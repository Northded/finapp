import os

class Config:
    SECRET_KEY = 'my-secret-key'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:5428@localhost/finmanager'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
