from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField, DateField, TextAreaField, BooleanField, DecimalField, validators  
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp, InputRequired, NumberRange, Length
from app.models import Account, Category
 

class RegisterForm(FlaskForm):
    name = StringField('Имя', validators=[
        DataRequired(), 
        Length(min=3, max=100)
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email()
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=8),
        Regexp(r'^(?=.*\d)(?=.*[!@#$%^&*]).{8,}$', message='Пароль должен содержать цифры и спецсимволы')
    ])
    confirm_password = PasswordField('Повторите пароль', validators=[
        DataRequired(), 
        EqualTo('password')
    ])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(), 
        Email()
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired()
    ])
    submit = SubmitField('Войти')

class TransactionForm(FlaskForm):
    type = SelectField('Тип операции', choices=[
        ('Доход', 'Доход'), 
        ('Расход', 'Расход')
        ], 
    validators=[DataRequired()])
    account = SelectField('Счет', validators=[DataRequired()])
    category = SelectField('Категория', validators=[DataRequired()])
    amount = DecimalField('Сумма', validators=[DataRequired()])
    date = DateField('Дата', validators=[DataRequired()])
    description = TextAreaField('Описание')
    submit = SubmitField('Сохранить')
    new_category = StringField('Новая категория', validators=[
        validators.Optional(), 
        validators.Length(max=50)
    ])

    def __init__(self, user_id, *args, **kwargs):  
        super(TransactionForm, self).__init__(*args, **kwargs)
        self.user_id = user_id
        self.update_choices()

    def update_choices(self): 
        # Обновление счетов
        self.account.choices = [
            (str(a.id), a.name) 
            for a in Account.query.filter_by(user_id=self.user_id).all()
        ]
        
        # Обновление категорий
        if self.type.data:
            self.category.choices = [
                (str(c.id), c.name) 
                for c in Category.query.filter(
                    (Category.user_id == self.user_id) |  
                    (Category.is_system == True)
                ).filter_by(type=self.type.data).all()
            ]
        else:
            self.category.choices = []
            
        

    def validate(self, **kwargs): 
        if not super().validate():
            return False
        
        if self.category.data == 'new' and not self.new_category.data:
            self.new_category.errors.append('Введите название категории')
            return False
            
        return True
    
class AccountForm(FlaskForm):
    name = StringField('Название счета', validators=[
        DataRequired(), 
        Length(max=50)
    ])
    currency = SelectField('Валюта', choices=[
        ('RUB', 'RUB')  
        ], 
    validators=[
        DataRequired()
    ])
    submit = SubmitField('Сохранить')

class CategoryForm(FlaskForm):
    name = StringField('Название категории', validators=[
        DataRequired(), 
        Length(max=50)
    ])
    type = SelectField('Тип операции', choices=[
        ('Доход', 'Доход'), 
        ('Расход', 'Расход')
        ], 
        validators=[
            DataRequired()
    ])
    is_system = BooleanField('Системная категория')
    submit = SubmitField('Сохранить')

class BudgetForm(FlaskForm):
    new_category = StringField('Категория', validators=[
        InputRequired(message="Введите название категории")
    ])
    limit_amount = DecimalField('Лимит', validators=[
        InputRequired(message="Укажите лимит")
    ])
    period = SelectField('Период', choices=[
        ('month', 'Месяц'), 
        ('year', 'Год')
    ])
    start_date = DateField('Дата начала', 
        format='%Y-%m-%d',
        validators=[InputRequired(message="Укажите дату начала")]
    )
    submit = SubmitField('Сохранить')

    # def __init__(self, *args, **kwargs):
    #     super(BudgetForm, self).__init__(*args, **kwargs)
    #     self.category.choices = [(str(c.id), c.name) for c in Category.query.filter_by(type='Расход').all()]

class GoalForm(FlaskForm):
    name = StringField('Название цели', validators=[
        DataRequired(), 
        Length(max=100)
    ])
    target_amount = FloatField('Целевая сумма', validators=[
        DataRequired(),
        NumberRange(min=0.01)
    ])
    deadline = DateField('Крайний срок', validators=[
        DataRequired()
    ])
    submit = SubmitField('Сохранить')

class AdminEditUserForm(FlaskForm):
    name = StringField('Имя', validators=[
        DataRequired(), 
        Length(max=100)
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email()
    ])
    role = SelectField('Роль', choices=[
        ('user', 'Обычный пользователь'), 
        ('admin', 'Администратор')
    ])
    submit = SubmitField('Сохранить')