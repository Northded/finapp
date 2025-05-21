from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file, current_app, jsonify, make_response
from flask_login import login_user, logout_user, current_user, login_required
from app.forms import LoginForm, RegisterForm, TransactionForm, AccountForm, GoalForm, BudgetForm, AdminEditUserForm, CategoryForm
from app.models import User, Transaction, Account, Category, Budget, Goal
from app import db
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal 
from io import StringIO, BytesIO, TextIOWrapper
import csv
from sqlalchemy import func, extract, and_, or_
from wtforms import StringField
import io  
import pandas as pd  
from dateutil.relativedelta import relativedelta

bp = Blueprint('main', __name__)

def init_routes(app):
    app.register_blueprint(bp)

@bp.route('/')
@login_required
def index():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    # расчет балданса
    balance = Decimal('0')
    
    # данные графиков
    expense_data = defaultdict(Decimal)
    income_data = defaultdict(Decimal)
    
    for t in transactions:
        if t.type == 'Доход':
            balance += t.amount
            income_data[t.category.name] += t.amount
        else:
            balance -= t.amount
            expense_data[t.category.name] += t.amount
    
    # преобразование данных
    expense_labels = list(expense_data.keys())
    expense_values = [float(v) for v in expense_data.values()]
    
    income_labels = list(income_data.keys())
    income_values = [float(v) for v in income_data.values()]
    
    recent_transactions = sorted(transactions, key=lambda x: x.date, reverse=True)[:5]
    
    return render_template(
        'index.html',
        balance=balance,
        recent_transactions=recent_transactions,
        expense_labels=expense_labels,
        expense_values=expense_values,
        income_labels=income_labels,
        income_values=income_values
    )

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Вход выполнен!', 'success')
            return redirect(url_for('main.index'))
        flash('Неверный email или пароль!', 'danger')
    return render_template('login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            name=form.name.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Пожалуйста, войдите.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('main.login'))


@bp.route('/transaction/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    form = TransactionForm(user_id=current_user.id)
    
    if form.validate_on_submit():
        amount = Decimal(str(form.amount.data))
        transaction_type = form.type.data
        category_id = None

        # Создание новой категории при необходимости
        if form.new_category.data:
            category = Category.query.filter_by(
                name=form.new_category.data, 
                user_id=current_user.id,
                type=form.type.data
            ).first()
            
            if not category:
                category = Category(
                    name=form.new_category.data,
                    type=form.type.data,
                    user_id=current_user.id,
                    is_system=False
                )
                db.session.add(category)
                db.session.commit()
            category_id = category.id
        else:
            category_id = int(form.category.data)

        # Проверка лимитов бюджета для расходов
        if transaction_type == 'Расход':
            now = datetime.utcnow()
            budgets = Budget.query.filter(
                Budget.category_id == category_id,
                Budget.user_id == current_user.id,
                or_(
                    and_(
                        Budget.period == 'month',
                        extract('month', Budget.start_date) == now.month,
                        extract('year', Budget.start_date) == now.year
                    ),
                    and_(
                        Budget.period == 'year',
                        extract('year', Budget.start_date) == now.year
                    )
                )
            ).all()

            for budget in budgets:
                start_date = budget.start_date
                if budget.period == 'month':
                    end_date = start_date + relativedelta(months=1)
                else:
                    end_date = start_date + relativedelta(years=1)
                spent = db.session.query(
                    func.coalesce(func.sum(Transaction.amount), Decimal('0'))
                ).filter(
                    Transaction.category_id == category_id,
                    Transaction.date >= start_date,
                    Transaction.date < end_date,
                    Transaction.type == 'Расход'
                ).scalar()

                if spent + amount > budget.limit_amount:
                    flash(f'Превышен лимит бюджета "{budget.category.name}"! Доступно: {budget.limit_amount - spent:.2f}₽', 'danger')
                    return render_template('add_transaction.html', form=form)

        transaction = Transaction(
            user_id=current_user.id,
            account_id=int(form.account.data),
            category_id=category_id,
            amount=amount,
            type=transaction_type,
            date=form.date.data,
            description=form.description.data
        )

        # Обновление баланса счета
        account = Account.query.get(form.account.data)
        if transaction_type == 'Доход':
            account.balance += amount
        else:
            account.balance -= amount

        db.session.add(transaction)
        db.session.commit()
        flash('Транзакция успешно добавлена!', 'success')
        return redirect(url_for('main.transactions'))
    
    return render_template('add_transaction.html', form=form)

@bp.route('/transactions')
@login_required
def transactions():
    type_filter = request.args.get('type', 'Все типы')
    category_filter = request.args.get('category', 'Все категории')
    date_filter = request.args.get('date', 'Все время')

    query = Transaction.query.filter_by(user_id=current_user.id)
    if type_filter != 'Все типы':
        query = query.filter_by(type=type_filter)
    if category_filter != 'Все категории':
        category = Category.query.filter_by(name=category_filter).first()
        query = query.filter_by(category_id=category.id)
    if date_filter == 'Неделя':
        query = query.filter(Transaction.date >= datetime.now() - timedelta(days=7))
    elif date_filter == 'Месяц':
        query = query.filter(Transaction.date >= datetime.now() - timedelta(days=30))
    elif date_filter == 'Год':
        query = query.filter(Transaction.date >= datetime.now() - timedelta(days=365))

    transactions = query.all()
    categories = Category.query.all()
    return render_template('transactions.html', transactions=transactions, categories=categories)

@bp.route('/transaction/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        abort(403)
    account = transaction.account
    if transaction.type == 'Доход':
        account.balance -= transaction.amount
    else:
        account.balance += transaction.amount
    db.session.delete(transaction)
    db.session.commit()
    flash('Транзакция удалена!', 'success')
    return redirect(url_for('main.transactions'))

@bp.route('/transaction/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        abort(403)
    
    form = TransactionForm(
        obj=transaction,
        user_id=current_user.id,
        account=transaction.account_id,
        category=transaction.category_id
    )
    
    if form.validate_on_submit():
        old_amount = transaction.amount
        new_amount = Decimal(str(form.amount.data))
        diff = new_amount - old_amount

        # Проверка лимитов бюджета для расходов
        if form.type.data == 'Расход':
            budgets = Budget.query.filter(
                Budget.category_id == transaction.category_id,
                Budget.user_id == current_user.id
            ).all()

            for budget in budgets:
                start_date = budget.start_date
                if budget.period == 'month':
                    end_date = start_date + relativedelta(months=1)
                else:
                    end_date = start_date + relativedelta(years=1)

                spent = db.session.query(
                    func.coalesce(func.sum(Transaction.amount), Decimal('0'))
                ).filter(
                    Transaction.category_id == transaction.category_id,
                    Transaction.date >= start_date,
                    Transaction.date < end_date,
                    Transaction.type == 'Расход'
                ).scalar()

                if (spent + diff) > budget.limit_amount:
                    flash(f'Превышен лимит бюджета "{budget.category.name}"! Доступно: {budget.limit_amount - spent:.2f}₽', 'danger')
                    return render_template('edit_transaction.html', form=form, transaction=transaction)

        # Обновление счетов
        old_account = transaction.account
        if transaction.type == 'Доход':
            old_account.balance -= old_amount
        else:
            old_account.balance += old_amount

        form.populate_obj(transaction)
        new_account = Account.query.get(form.account.data)
        
        if transaction.type == 'Доход':
            new_account.balance += new_amount
        else:
            new_account.balance -= new_amount

        db.session.commit()
        flash('Транзакция успешно обновлена!', 'success')
        return redirect(url_for('main.transactions'))
    
    return render_template('edit_transaction.html', form=form, transaction=transaction)

@bp.route('/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    form = AccountForm()
    if form.validate_on_submit():
        account = Account(
            user_id=current_user.id,
            name=form.name.data,
            currency=form.currency.data
        )
        db.session.add(account)
        db.session.commit()
        flash('Счет создан!', 'success')
        return redirect(url_for('main.accounts'))
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('accounts.html', form=form, accounts=accounts)

@bp.route('/account/delete/<int:id>', methods=['POST'])
@login_required
def delete_account(id):
    account = Account.query.get_or_404(id)
    if account.user_id != current_user.id:
        abort(403)
    if Transaction.query.filter_by(account_id=account.id).count() > 0:
        flash('Нельзя удалить счет с транзакциями!', 'error')
        return redirect(url_for('main.accounts'))
    db.session.delete(account)
    db.session.commit()
    flash('Счет удален!', 'success')
    return redirect(url_for('main.accounts'))

@bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if current_user.role != 'admin':
        abort(403)
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(
            user_id=None if form.is_system.data else current_user.id,
            name=form.name.data,
            type=form.type.data,
            is_system=form.is_system.data
        )
        db.session.add(category)
        db.session.commit()
        flash('Категория добавлена!', 'success')
        return redirect(url_for('categories'))
    categories = Category.query.all()
    return render_template('categories.html', form=form, categories=categories)

@bp.route('/category/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    if current_user.role != 'admin':
        abort(403)
    category = Category.query.get_or_404(id)
    if category.is_system:
        flash('Нельзя удалить системную категорию!', 'error')
        return redirect(url_for('main.categories'))
    if Transaction.query.filter_by(category_id=category.id).count() > 0:
        flash('Нельзя удалить категорию с транзакциями!', 'error')
        return redirect(url_for('main.categories'))
    db.session.delete(category)
    db.session.commit()
    flash('Категория удалена!', 'success')
    return redirect(url_for('main.categories'))

@bp.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    form = BudgetForm()
    query = current_user.budgets.order_by(Budget.id.desc())  
    budgets_data = query.all()  

    if form.validate_on_submit():
        try:
            category_name = form.new_category.data.strip().capitalize()
            category = Category.query.filter(
                Category.name == category_name,
                Category.user_id == current_user.id,
                Category.type == 'Расход'
            ).first()

            if not category:
                category = Category(
                    name=category_name,
                    type='Расход',
                    user_id=current_user.id,
                    is_system=False
                )
                db.session.add(category)
                db.session.flush()  # сохраниение без коммита для получения айди

            # создание бюджета
            budget = Budget(
                user_id=current_user.id,
                category_id=category.id,
                limit_amount=form.limit_amount.data,
                period=form.period.data,
                start_date=form.start_date.data
            )
            
            db.session.add(budget)
            db.session.commit()
            flash('Бюджет успешно создан!', 'success')
            return redirect(url_for('main.budgets'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании бюджета: {str(e)}', 'danger')

    return render_template('budgets.html',
        form=form,
        budgets=query.all()  
    )

@bp.route('/budget/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_budget(id):
    budget = Budget.query.get_or_404(id)
    
    if budget.user_id != current_user.id:
        abort(403)

    # блок поле категории
    class ReadonlyCategoryForm(BudgetForm):
        new_category = StringField('Категория', render_kw={'readonly': True})

    form = ReadonlyCategoryForm(obj=budget)
    form.new_category.data = budget.category.name  #текущие значение

    if form.validate_on_submit():
        try:
            budget.limit_amount = form.limit_amount.data
            budget.period = form.period.data
            budget.start_date = form.start_date.data
            
            db.session.commit()
            flash('Бюджет успешно обновлен!', 'success')
            return redirect(url_for('main.budgets'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления: {str(e)}', 'danger')

    return render_template('edit_budget.html', 
        form=form,
        budget=budget
    )
@bp.route('/budget/delete/<int:id>', methods=['POST'])
@login_required
def delete_budget(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        abort(403)
    db.session.delete(budget)
    db.session.commit()
    flash('Бюджет удален!', 'success')
    return redirect(url_for('main.budgets'))

@bp.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    form = GoalForm()
    if form.validate_on_submit():
        goal = Goal(
            user_id=current_user.id,
            name=form.name.data,
            target_amount=form.target_amount.data,
            deadline=form.deadline.data
        )
        db.session.add(goal)
        db.session.commit()
        flash('Цель создана!', 'success')
        return redirect(url_for('main.goals'))
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return render_template('goals.html', form=form, goals=goals)

@bp.route('/goal/<int:id>/add_progress', methods=['POST'])
@login_required
def add_goal_progress(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        abort(403)

    try:
        amount = Decimal(request.form.get('amount'))
        account_id = int(request.form.get('account'))  
    except:
        flash('Некорректные данные', 'danger')
        return redirect(url_for('main.goals'))

    # получение счета и проверка баланса
    account = Account.query.get(account_id)
    if account.balance < amount:
        flash('Недостаточно средств на счете', 'danger')
        return redirect(url_for('main.goals'))

    # поиск или создание цели
    category = Category.query.filter_by(
        name=goal.name, 
        type='Расход', 
        user_id=current_user.id
    ).first()

    if not category:
        category = Category(
            name=goal.name,
            type='Расход',
            user_id=current_user.id,
            is_system=False
        )
        db.session.add(category)
        db.session.flush()

    # транзакция
    transaction = Transaction(
        user_id=current_user.id,
        account_id=account_id,
        category_id=category.id,
        amount=amount,
        type='Расход',
        date=datetime.utcnow(),
        description=f"Пополнение цели: {goal.name}"
    )

    # обновление баланса счета и прогресса цели
    account.balance -= amount
    goal.current_progress += amount

    db.session.add(transaction)
    db.session.commit()
    flash('Прогресс обновлен! Транзакция создана', 'success')
    return redirect(url_for('main.goals'))

@bp.route('/goal/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        abort(403)
    
    form = GoalForm(obj=goal)  # Автозаполнение формы
    
    if form.validate_on_submit():
        form.populate_obj(goal)  # Обновление объекта
        db.session.commit()
        flash('Цель обновлена!', 'success')
        return redirect(url_for('main.goals'))
    
    return render_template('edit_goal.html', form=form, goal=goal)

@bp.route('/goal/delete/<int:id>', methods=['POST'])
@login_required
def delete_goal(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        abort(403)
    db.session.delete(goal)
    db.session.commit()
    flash('Цель удалена!', 'success')
    return redirect(url_for('main.goals'))

@bp.route('/analytics')
@login_required
def analytics():
    # данные пользователя
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    month_ago = datetime.now() - timedelta(days=30)
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= month_ago
    ).all()
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    goals = Goal.query.filter_by(user_id=current_user.id).all()

    # проверка, есть ли данные для аналитики
    has_data = any([
        len(accounts) > 0,
        len(transactions) > 0, 
        len(budgets) > 0,
        len(goals) > 0
    ])

    # данные для графиков
    expense_data = defaultdict(Decimal)
    income_data = defaultdict(Decimal)
    
    for t in transactions:
        if t.type == 'Расход':
            expense_data[t.category.name] += t.amount
        else:
            income_data[t.category.name] += t.amount

    # статус бюджетов
    budget_status = []
    for budget in budgets:
        spent = sum(
            t.amount for t in transactions 
            if t.category_id == budget.category_id 
            and t.type == 'Расход'
        )
        budget_status.append({
            'category': budget.category.name,
            'limit': budget.limit_amount,
            'spent': spent,
            'remaining': budget.limit_amount - spent
        })

    return render_template(
        'analytics.html',
        has_data=has_data,  # Флаг наличия данных
        accounts=accounts,
        category_data=expense_data,  # Данные для графика расходов
        income_data=income_data,     # Данные для графика доходов
        budget_status=budget_status,
        goals=goals
    )

@bp.route('/export_transactions')
@login_required
def export_transactions():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    data = [{
        'Дата': t.date,
        'Счет': t.account.name,
        'Категория': t.category.name,
        'Сумма': t.amount,
        'Тип': t.type,
        'Описание': t.description
    } for t in transactions]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name='transactions.xlsx', as_attachment=True)

@bp.route('/export_analytics')
@login_required
def export_analytics():
    try:
        # сбор данных
        user_id = current_user.id
        data = {
            'transactions': Transaction.query.filter_by(user_id=user_id).all(),
            'accounts': Account.query.filter_by(user_id=user_id).all(),
            'budgets': Budget.query.filter_by(user_id=user_id).all(),
            'goals': Goal.query.filter_by(user_id=user_id).all()
        }

        # бинарный буфер и BOM
        csv_buffer = BytesIO()
        csv_buffer.write(b'\xef\xbb\xbf')  # UTF-8 BOM

        # TextIOWrapper с правильной кодировкой
        text_wrapper = TextIOWrapper(
            csv_buffer,
            encoding='utf-8-sig',
            write_through=True,
            newline=''
        )

        writer = csv.writer(text_wrapper, delimiter=';')

        # 1. Транзакции
        writer.writerow(['=== ТРАНЗАКЦИИ ==='])
        writer.writerow([
            'Дата', 'Тип', 'Категория', 
            'Сумма (руб)', 'Счет', 'Описание'
        ])
        for t in data['transactions']:
            writer.writerow([
                t.date.strftime('%d.%m.%Y'),
                t.type,
                t.category.name,
                f"{t.amount:.2f}".replace('.', ','),
                t.account.name,
                t.description or '-'
            ])
        writer.writerow([])

        # 2. Счета
        writer.writerow(['=== СЧЕТА ==='])
        writer.writerow(['Название', 'Баланс (руб)', 'Валюта'])
        for a in data['accounts']:
            writer.writerow([
                a.name,
                f"{a.balance:.2f}".replace('.', ','),
                a.currency
            ])
        writer.writerow([])

        # 3. Бюджеты
        writer.writerow(['=== БЮДЖЕТЫ ==='])
        writer.writerow(['Категория', 'Лимит (руб)', 'Потрачено (руб)', 'Остаток (руб)'])
        for b in data['budgets']:
            spent = sum(
                t.amount for t in data['transactions'] 
                if t.category_id == b.category_id and t.type == 'Расход'
            )
            writer.writerow([
                b.category.name,
                f"{b.limit_amount:.2f}".replace('.', ','),
                f"{spent:.2f}".replace('.', ','),
                f"{(b.limit_amount - spent):.2f}".replace('.', ',')
            ])
        writer.writerow([])

        # 4. Цели
        writer.writerow(['=== ЦЕЛИ ==='])
        writer.writerow(['Название', 'Цель (руб)', 'Прогресс (руб)', '% выполнения'])
        for g in data['goals']:
            progress_percent = (g.current_progress / g.target_amount * 100) if g.target_amount != 0 else 0
            writer.writerow([
                g.name,
                f"{g.target_amount:.2f}".replace('.', ','),
                f"{g.current_progress:.2f}".replace('.', ','),
                f"{progress_percent:.2f}%"
            ])

        # запись
        text_wrapper.flush()
        csv_buffer.seek(0)

        # ответ
        response = make_response(csv_buffer.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
        response.headers['Content-Disposition'] = \
            f'attachment; filename=analytics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response

    except Exception as e:
        flash(f'Ошибка при выгрузке: {str(e)}', 'danger')
        current_app.logger.error(f'Export error: {str(e)}')
        return redirect(url_for('main.analytics'))
    
@bp.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        abort(403)
    
    users = User.query.all()
    stats = []
    
    for user in users:
        stats.append({
            'user': user,
            'transactions': Transaction.query.filter_by(user_id=user.id).count(),
            'accounts': Account.query.filter_by(user_id=user.id).count(),
            'goals': Goal.query.filter_by(user_id=user.id).count()
        })
    
    return render_template('admin_panel.html', stats=stats)

@bp.route('/admin/delete_user/<int:id>', methods=['POST'])
@login_required
def admin_delete_user(id):
    if current_user.role != 'admin':
        abort(403)
        
    user = User.query.get_or_404(id)
    if user == current_user:
        flash('Нельзя удалить самого себя!', 'danger')
        return redirect(url_for('main.admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удален!', 'success')
    return redirect(url_for('main.admin_panel'))

@bp.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(id):
    if current_user.role != 'admin':
        abort(403)
        
    user = User.query.get_or_404(id)
    form = AdminEditUserForm(obj=user)
    
    if form.validate_on_submit():
        form.populate_obj(user)
        db.session.commit()
        flash('Данные пользователя обновлены!', 'success')
        return redirect(url_for('main.admin_panel'))
    
    return render_template('edit_user.html', form=form, user=user)

@bp.route('/admin/export_users_csv')
@login_required
def admin_export_csv():
    if current_user.role != 'admin':
        abort(403)
    
    users = User.query.all()
    
    # CSV-буфер
    csv_buffer = BytesIO()
    csv_buffer.write(b'\xef\xbb\xbf')  # BOM для UTF-8
    text_wrapper = TextIOWrapper(csv_buffer, encoding='utf-8-sig', write_through=True)
    writer = csv.writer(text_wrapper, delimiter=';')
    
    # Заголовки
    writer.writerow([
        'ID', 'Имя', 'Email', 'Роль', 
        'Дата регистрации', 'Транзакций', 
        'Счетов', 'Целей'
    ])
    
    # Данные
    for user in users:
        writer.writerow([
            user.id,
            user.name,
            user.email,
            user.role,
            user.created_at.strftime('%d.%m.%Y %H:%M'),
            Transaction.query.filter_by(user_id=user.id).count(),
            Account.query.filter_by(user_id=user.id).count(),
            Goal.query.filter_by(user_id=user.id).count()
        ])
    
    text_wrapper.flush()
    csv_buffer.seek(0)
    
    # ответ
    response = make_response(csv_buffer.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=users_export_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@bp.route('/get_categories')
@login_required
def get_categories():
    type_filter = request.args.get('type', 'Доход')
    categories = Category.query.filter(
        (Category.user_id == current_user.id) | Category.is_system.is_(True),
        Category.type == type_filter
    ).all()
    return jsonify({
        'categories': [{'id': c.id, 'name': c.name} for c in categories]
    })