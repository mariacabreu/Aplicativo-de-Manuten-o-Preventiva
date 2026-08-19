from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    plan_type = db.Column(db.String(20), default='free')
    reminder_frequency = db.Column(db.String(50), default='biweekly')
    phone = db.Column(db.String(20), nullable=True)
    avatar = db.Column(db.Text, nullable=True)  # Base64 encoded image or URL

    notifications_enabled = db.Column(db.Boolean, default=True)
    notif_maintenance = db.Column(db.Boolean, default=True)
    notif_obd = db.Column(db.Boolean, default=True)
    notif_fuel = db.Column(db.Boolean, default=True)
    notif_tips = db.Column(db.Boolean, default=True)
    notif_milestones = db.Column(db.Boolean, default=True)
    notif_system = db.Column(db.Boolean, default=True)

    premium_ai_insights = db.Column(db.Boolean, default=True)
    premium_predictive = db.Column(db.Boolean, default=True)
    premium_driving_analysis = db.Column(db.Boolean, default=True)
    premium_seasonal = db.Column(db.Boolean, default=True)
    premium_smart_frequency = db.Column(db.Boolean, default=True)
    last_notif_generation = db.Column(db.String(50), nullable=True)

    vehicles = db.relationship('Vehicle', backref='owner', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'is_premium': self.is_premium,
            'plan_type': self.plan_type,
            'reminder_frequency': self.reminder_frequency,
            'avatar_url': self.avatar,
            'avatar': self.avatar,
            'notifications_enabled': bool(self.notifications_enabled),
            'notif_maintenance': bool(self.notif_maintenance),
            'notif_obd': bool(self.notif_obd),
            'notif_fuel': bool(self.notif_fuel),
            'notif_tips': bool(self.notif_tips),
            'notif_milestones': bool(self.notif_milestones),
            'notif_system': bool(self.notif_system),
            'premium_ai_insights': bool(self.premium_ai_insights),
            'premium_predictive': bool(self.premium_predictive),
            'premium_driving_analysis': bool(self.premium_driving_analysis),
            'premium_seasonal': bool(self.premium_seasonal),
            'premium_smart_frequency': bool(self.premium_smart_frequency),
            'last_notif_generation': self.last_notif_generation,
        }


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    transmission = db.Column(db.String(20))
    mileage = db.Column(db.Integer)
    fuel_type = db.Column(db.String(20))
    engine_type = db.Column(db.String(50))
    usage_type = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    last_oil_change = db.Column(db.Integer, default=0)
    last_belt_change = db.Column(db.Integer, default=0)
    last_brake_change = db.Column(db.Integer, default=0)
    maintenance_history = db.relationship('MaintenanceHistory', backref='vehicle', lazy=True, cascade='all, delete-orphan')
    obd_scans = db.relationship('OBDScan', backref='vehicle', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'brand': self.brand,
            'model': self.model,
            'year': self.year,
            'transmission': self.transmission,
            'mileage': self.mileage,
            'fuel_type': self.fuel_type,
            'engine_type': self.engine_type,
            'usage_type': self.usage_type,
            'last_oil_change': self.last_oil_change,
            'last_belt_change': self.last_belt_change,
            'last_brake_change': self.last_brake_change,
            'maintenance_history': [h.to_dict() for h in self.maintenance_history]
        }


class MaintenanceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    item = db.Column(db.String(100), nullable=False)
    last_km = db.Column(db.Integer, nullable=False)
    last_date = db.Column(db.String(20))
    cost = db.Column(db.Float, default=0.0)
    liters = db.Column(db.Float, default=0.0)

    def to_dict(self):
        return {
            'id': self.id,
            'item': self.item,
            'last_km': self.last_km,
            'last_date': self.last_date,
            'cost': self.cost,
            'liters': self.liters
        }


class OBDScan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    scan_date = db.Column(db.String(50), nullable=False)
    dtc_codes = db.Column(db.JSON, default=[])
    live_data = db.Column(db.JSON, default={})
    connected_device = db.Column(db.String(100))

    def to_dict(self):
        return {
            'id': self.id,
            'vehicle_id': self.vehicle_id,
            'scan_date': self.scan_date,
            'dtc_codes': self.dtc_codes,
            'live_data': self.live_data,
            'connected_device': self.connected_device
        }


NOTIFICATION_TYPES = {
    'MAINTENANCE_REMINDER': 'maintenance',
    'OBD_ALERT': 'obd',
    'VEHICLE_TIP': 'tip',
    'MILESTONE': 'milestone',
    'PREMIUM_INSIGHT': 'premium',
    'FUEL_ALERT': 'fuel',
    'SYSTEM': 'system',
}

NOTIFICATION_PRIORITY = {
    'CRITICAL': 'critical',
    'HIGH': 'high',
    'MEDIUM': 'medium',
    'LOW': 'low',
}


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(40), default=NOTIFICATION_TYPES['SYSTEM'])
    priority = db.Column(db.String(20), default=NOTIFICATION_PRIORITY['MEDIUM'])
    read = db.Column(db.Boolean, default=False, nullable=False)
    ai_generated = db.Column(db.Boolean, default=False, nullable=False)
    premium_only = db.Column(db.Boolean, default=False, nullable=False)
    action = db.Column(db.String(80), nullable=True)
    payload = db.Column(db.JSON, default={})
    created_at = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.Index('idx_notif_user_read', 'user_id', 'read'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'vehicle_id': self.vehicle_id,
            'title': self.title,
            'description': self.description,
            'type': self.notification_type,
            'priority': self.priority,
            'read': bool(self.read),
            'ai_generated': bool(self.ai_generated),
            'premium_only': bool(self.premium_only),
            'action': self.action,
            'payload': self.payload or {},
            'time': self.created_at,
            'created_at': self.created_at,
        }

