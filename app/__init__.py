from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    csrf.init_app(app)
    migrate.init_app(app, db)

    from app.routes import init_routes
    init_routes(app)

    # Регистрируем user_loader для Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def init_default_categories():
        from app.models import Category
        with app.app_context():
            if not Category.query.filter_by(is_system=True).first():
                default_categories = [
                    Category(name='Зарплата', type='Доход', is_system=True),
                    Category(name='Продукты', type='Расход', is_system=True),
                    Category(name='Транспорт', type='Расход', is_system=True)
                ]
                db.session.bulk_save_objects(default_categories)
                db.session.commit()

    # Вызываем инициализацию категорий после миграций
    with app.app_context():
        init_default_categories()

    return app