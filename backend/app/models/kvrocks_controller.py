"""
KVrocks Controller model
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ControllerStatus(str, enum.Enum):
    """Controller connection status"""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class KVrocksController(Base):
    """KVrocks Controller instance"""
    __tablename__ = 'kvrocks_controllers'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    address = Column(String(255), nullable=False, unique=True)  # http://host:port
    status = Column(Enum(ControllerStatus), default=ControllerStatus.UNKNOWN)
    version = Column(String(50))  # Controller version
    description = Column(String(500))

    # Health check info
    last_check_at = Column(DateTime)
    last_error = Column(Text)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clusters = relationship('Cluster', back_populates='controller',
                          foreign_keys='Cluster.controller_id')
