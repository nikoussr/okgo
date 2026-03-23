from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Enum as SQLEnum, BigInteger, \
    CheckConstraint, Index
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import enum


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ========== ENUMS ==========
class UserRole(str, enum.Enum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    AGENT = "agent"
    ADMIN = "admin"


class CarClass(str, enum.Enum):
    PASSENGER_CAR = "passenger_car"
    MICROBUS = "microbus"
    BUSINESS = "business"
    BUS = "bus"


class TripStatus(str, enum.Enum):
    PUBLISHED = "published"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TripResponseStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TripType(str, enum.Enum):
    OWN = "own"  # Собственная поездка водителя
    DELEGATED = "delegated"  # Поездка, переданная другому водителю


# ========== MODELS ==========
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(200), nullable=True)
    first_name = Column(String(200), nullable=True)
    last_name = Column(String(200), nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False) # Агент, водитель
    phone_number = Column(String(20), nullable=True) # Номер телефона для связи
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False) # Имеет ли пользователь подписку
    subscription_exp = Column(DateTime(timezone=True), nullable=True) # Дата, когда истекает подписка
    sbp_bank = Column(String(50), nullable=True) # Банк, куда принимать комиссию
    sbp_phone_number = Column(String(20), nullable=True) # Номер телефона для переврда комиссии
    organization = Column(String(200), nullable=True) # Название организации пользователя для аналитики
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    vehicles = relationship("Vehicle", back_populates="driver", cascade="all, delete-orphan")

    # Разделяем поездки на созданные и выполненные
    trips_created = relationship("Trip", foreign_keys="Trip.creator_id", back_populates="creator")
    trips_driven = relationship("Trip", foreign_keys="Trip.driver_id", back_populates="driver")

    # Отзывы
    reviews_received = relationship("Review", foreign_keys="Review.driver_id", back_populates="driver")
    reviews_given = relationship("Review", foreign_keys="Review.passenger_id", back_populates="passenger")

    # Финансовые операции
    financial_operations = relationship("FinancialOperation", back_populates="user")

    referrals_given = relationship(
        "Referral",
        foreign_keys="Referral.referrer_id",
        back_populates="referrer"
    )
    referrals_received = relationship(
        "Referral",
        foreign_keys="Referral.referral_id",
        back_populates="referral"
    )

    # Отклики на поездки (для водителей)
    trip_responses = relationship("TripResponse", back_populates="driver")

    __table_args__ = (
        CheckConstraint('rating_avg >= 0 AND rating_avg <= 5', name='check_rating_avg_range'),
        CheckConstraint('rating_count >= 0', name='check_rating_count_non_negative'),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String(50), nullable=False)
    license_plate = Column(String(20), nullable=False, unique=True)
    additional_info = Column(String(200), nullable=True)
    car_class = Column(SQLEnum(CarClass), nullable=False)
    photo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    driver = relationship("User", back_populates="vehicles")
    trips = relationship("Trip", back_populates="vehicle")

    __table_args__ = (
        CheckConstraint('year >= 1900 AND year <= 2100', name='check_year_range'),
    )


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Кто создал поездку
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # Кто выполняет поездку
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=True)

    # Тип поездки
    trip_type = Column(SQLEnum(TripType), nullable=False, default=TripType.OWN)

    # Поля делегирования
    delegation_commission = Column(Float, default=0.0)  # Комиссия создателя
    is_delegation_active = Column(Boolean, default=True)  # Активен ли поиск водителя

    # Основные данные поездки
    from_address = Column(String(500), nullable=False)
    to_address = Column(String(500), nullable=False)
    departure_datetime = Column(DateTime(timezone=True), nullable=False)
    price = Column(Float, nullable=True)  # Общая цена за поездку
    total_seats = Column(Integer, nullable=False)
    passenger_phone_number = Column(String(20), nullable=True)
    car_class = Column(SQLEnum(CarClass), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(TripStatus), default=TripStatus.PUBLISHED)
    channel_message_id = Column(Integer, nullable=True)  # ID сообщения в канале
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[creator_id], back_populates="trips_created")
    driver = relationship("User", foreign_keys=[driver_id], back_populates="trips_driven")
    vehicle = relationship("Vehicle", back_populates="trips")
    trip_responses = relationship("TripResponse", back_populates="trip")
    reviews = relationship("Review", back_populates="trip")

    __table_args__ = (
        Index('idx_trips_route_date', 'from_address', 'to_address', 'departure_datetime'),
        Index('idx_trips_creator_status', 'creator_id', 'status'),
        Index('idx_trips_driver_status', 'driver_id', 'status'),
        Index('idx_trips_delegation', 'trip_type', 'is_delegation_active', 'status'),
        CheckConstraint('total_seats > 0', name='check_total_seats_positive'),
        CheckConstraint('price IS NULL OR price > 0', name='check_price_positive'),
        CheckConstraint('delegation_commission >= 0', name='check_commission_non_negative'),
    )


class TripResponse(Base):
    __tablename__ = "trip_responses"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    proposed_price = Column(Float, nullable=True)

    status = Column(SQLEnum(TripResponseStatus), default=TripResponseStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="trip_responses")
    driver = relationship("User", back_populates="trip_responses")
    vehicle = relationship("Vehicle")

    __table_args__ = (
        Index('idx_trip_responses_trip_status', 'trip_id', 'status'),
        Index('idx_trip_responses_driver_status', 'driver_id', 'status'),
        # Уникальный отклик водителя на поездку
        Index('idx_trip_responses_unique', 'trip_id', 'driver_id', unique=True),
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="reviews")
    passenger = relationship("User", foreign_keys=[passenger_id], back_populates="reviews_given")
    driver = relationship("User", foreign_keys=[driver_id], back_populates="reviews_received")

    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        # Один отзыв на поездку от пассажира
        Index('idx_reviews_trip_passenger', 'trip_id', 'passenger_id', unique=True),
    )


class FinancialOperation(Base):
    __tablename__ = "financial_operations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    external_payment_id = Column(String(255), nullable=True)
    telegram_payment_charge_id = Column(String(255), nullable=True)  # Добавляем для Telegram Payments
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    provider_payload = Column(Text, nullable=True)  # Для хранения данных от провайдера

    user = relationship("User", back_populates="financial_operations")

    __table_args__ = (
        CheckConstraint('amount != 0', name='check_amount_non_zero'),
    )

class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    referral_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships - ИСПРАВЛЕНО
    referrer = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals_given"  # Изменить в User
    )
    referral = relationship(
        "User",
        foreign_keys=[referral_id],
        back_populates="referrals_received"  # Изменить в User
    )

    __table_args__ = (
        Index('idx_referrer_id', 'referrer_id'),
        Index('idx_referral_id', 'referral_id'),
    )

