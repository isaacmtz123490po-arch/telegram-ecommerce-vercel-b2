
from os import environ

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, LargeBinary, String, Boolean, text
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import relationship
from sqlalchemy.orm import DeclarativeBase



class Base(DeclarativeBase):
    pass

class Customer(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    username = Column(String(30), nullable=False)
    password_hash = Column(String(64))
    is_admin = Column(Boolean, nullable=False, server_default=text("'0'"))


class Photo(Base):
    __tablename__ = 'photo'

    id = Column(String(150), primary_key=True)
    image_blob = Column(LargeBinary)


class Category(Base):
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(30), nullable=False)
    description = Column(String(500), nullable=False)
    tags = Column(String(100))
    image_id = Column(ForeignKey('photo.id'), index=True)

    image = relationship('Photo')


class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (
        Index('name', 'name', 'description'),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(30), nullable=False)
    description = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    quantity_in_stock = Column(Integer, nullable=False)
    quantity_purchased = Column(Integer, nullable=False)
    category_id = Column(ForeignKey('category.id'), nullable=False, index=True)
    image_id = Column(ForeignKey('photo.id'), index=True)

    category = relationship('Category')
    image = relationship('Photo')


class Order(Base):
    __tablename__ = 'orders'

    id = Column(String(150), primary_key=True)
    price = Column(Float, nullable=False)
    user_id = Column(ForeignKey('customers.id', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, index=True)
    product_id = Column(ForeignKey('products.id', ondelete='RESTRICT', onupdate='RESTRICT'), nullable=False, index=True)
    rating = Column(Integer)

    product = relationship('Product')
    user = relationship('Customer')

# Supabase uses PostgreSQL. For legacy MySQL deployments, set DB_DIALECT=mysql.
db_dialect = environ.get("DB_DIALECT", "postgresql").strip().lower() or "postgresql"
db_user = environ["DB_USER"]
db_password = environ["DB_PASSWORD"]
db_host = environ["DB_HOST"]
db_name = environ["DB_NAME"]
# Vercel may omit the port or provide it as an empty string.
default_port = "3306" if db_dialect in ("mysql", "mysql+pymysql") else "5432"
db_port = int(environ.get("DB_PORT") or default_port)

if db_dialect in ("mysql", "mysql+pymysql"):
    db_url = URL.create(
        "mysql+pymysql", username=db_user, password=db_password,
        host=db_host, port=db_port, database=db_name,
    )
    engine = create_engine(db_url, pool_pre_ping=True)
elif db_dialect in ("postgres", "postgresql", "postgresql+psycopg2"):
    db_url = URL.create(
        "postgresql+psycopg2", username=db_user, password=db_password,
        host=db_host, port=db_port, database=db_name,
        query={"sslmode": environ.get("DB_SSLMODE", "require")},
    )
    engine = create_engine(db_url, pool_pre_ping=True)
else:
    raise ValueError("DB_DIALECT must be 'postgresql' or 'mysql'")
Session = sessionmaker(engine)

