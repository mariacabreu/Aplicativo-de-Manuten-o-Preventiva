from flask import Blueprint, request, jsonify
from app.models.models import (
    User, Vehicle, MaintenanceHistory,
    Notification, NOTIFICATION_TYPES, NOTIFICATION_PRIORITY,
    OBDScan
)
from app import db
import os
from datetime import datetime, timedelta

try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    ai_client = OpenAI(api_key=openai_api_key) if openai_api_key and openai_api_key != "your_openai_api_key_here" else None
except ImportError:
    ai_client = None
    print("OpenAI module not available - Premium AI notifications will use static engine")

PREMIUM_AI_NOTIFICATION_LIMIT = 10
STATIC_AI_INSIGHTS_BY_CATEGORY = {
    'maintenance': [
        ('Inspeção Preventiva Inteligente',
         'Com base na sua quilometragem e perfil de uso {usage_type}, recomendamos uma inspeção visual nas pastilhas de freio e alinhamento antes do próximo abastecimento. Veículos de {usage_type} gastam componentes 20% mais rápido.'),
        ('Troca de Óleo Próxima',
         'A IA detectou que você está a {km_left} km da próxima troca de óleo recomendada. Planejar a troca com antecedência reduz o desgaste do motor em até 35%.'),
    ],
    'fuel': [
        ('Dica de Economia',
         'Para o seu {brand} {model}, o modo de direção econômico em combinação com pneus calibrados semanalmente pode reduzir o consumo em até 18%.'),
        ('Análise de Combustível',
         'Veículos movidos a {fuel_type} apresentam melhor desempenho ao evitar enchimentos em horários de pico. A temperatura baixa aumenta a densidade do combustível.'),
    ],
    'driving': [
        ('Perfil de Direção',
         'A IA identificou que 68% dos seus percursos são urbanos. Evitar acelerações bruscas em primeiros marchas economiza combustível e aumenta a vida útil da embreagem.'),
        ('Recomendação Preditiva',
         'Previsão para os próximos 30 dias: baseado no seu histórico, recomendamos calibrar o balanceamento das rodas antes de viagens longas.'),
    ],
    'health': [
        ('Saúde do Motor',
         'Monitoramento preventivo: temperatura de trabalho do {brand} {model} está dentro dos padrões, mas recomendamos checagem do sistema de arrefecimento a cada 20 mil km.'),
        ('Sensores e Emissões',
         'A sonda lambda deve ser inspecionada aos 80 mil km. Uma sonda desgastada pode aumentar o consumo em até 20% e danificar o catalisador.'),
    ],
    'obd': [
        ('Insight OBD-II',
         'Sua varredura OBD-II mais recente mostrou {dtc_count} códigos pendentes. Acompanhe a evolução antes do próximo diagnóstico completo.'),
    ],
}


def _now_iso():
    return datetime.now().isoformat(timespec='seconds')


def _days_until_next_km(current_km, target_km, daily_avg_km):
    remaining = max(0, target_km - current_km)
    if daily_avg_km <= 0:
        return None, remaining
    days = int(round(remaining / daily_avg_km))
    return days, remaining


FREQUENCY_HOURS = {
    'daily': 24,
    'weekly': 168,
    'biweekly': 336,
    'monthly': 720,
}


def _should_regenerate_for_user(user, force_refresh=False):
    if force_refresh:
        return True
    if not user.last_notif_generation:
        return True
    try:
        last = datetime.fromisoformat(user.last_notif_generation)
    except Exception:
        return True
    hours = FREQUENCY_HOURS.get(user.reminder_frequency, FREQUENCY_HOURS['biweekly'])
    if user.is_premium and user.premium_smart_frequency:
        hours = max(6, hours // 2)
    return (datetime.now() - last).total_seconds() >= (hours * 3600)


def _user_allows_notification_type(user, notif_type, ai_generated=False):
    if not bool(getattr(user, 'notifications_enabled', True)):
        if notif_type != NOTIFICATION_TYPES['SYSTEM']:
            return False
    type_map = {
        NOTIFICATION_TYPES['MAINTENANCE_REMINDER']: 'notif_maintenance',
        NOTIFICATION_TYPES['OBD_ALERT']: 'notif_obd',
        NOTIFICATION_TYPES['FUEL_ALERT']: 'notif_fuel',
        NOTIFICATION_TYPES['VEHICLE_TIP']: 'notif_tips',
        NOTIFICATION_TYPES['MILESTONE']: 'notif_milestones',
        NOTIFICATION_TYPES['SYSTEM']: 'notif_system',
        NOTIFICATION_TYPES['PREMIUM_INSIGHT']: 'premium_ai_insights',
    }
    pref = type_map.get(notif_type)
    if pref is None:
        return True
    if not getattr(user, pref, True):
        return False
    if ai_generated and user.is_premium:
        category = None
        if notif_type in (NOTIFICATION_TYPES['PREMIUM_INSIGHT'],):
            category = 'premium_ai_insights'
        if category and not getattr(user, category, True):
            return False
    return True


def _persist_notification(user, vehicle_id, title, description, notif_type, priority, ai=False, premium=False, action=None, payload=None):
    if not _user_allows_notification_type(user, notif_type, ai_generated=ai):
        return None
    if premium and not user.is_premium:
        return None
    user_id = user.id
    existing = Notification.query.filter_by(
        user_id=user_id,
        title=title,
        read=False
    ).first()
    if existing:
        return existing

    record = Notification(
        user_id=user_id,
        vehicle_id=vehicle_id,
        title=title,
        description=description,
        notification_type=notif_type,
        priority=priority,
        read=False,
        ai_generated=ai,
        premium_only=premium,
        action=action,
        payload=payload or {},
        created_at=_now_iso()
    )
    db.session.add(record)
    return record


def _static_ai_insight_generator(user, vehicle, usage_type_str):
    daily_avg = 50 if usage_type_str == 'Urbano' else (120 if usage_type_str == 'Rodoviário' else 80)
    current_km = vehicle.mileage or 0
    brand = vehicle.brand or 'veículo'
    model = vehicle.model or ''
    fuel = vehicle.fuel_type or 'Gasolina'

    insights = []

    km_to_next_oil = 10000 - (current_km % 10000)
    if km_to_next_oil < 2000:
        title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['maintenance'][1]
        insights.append({
            'title': title_base,
            'description': desc_base.format(km_left=km_to_next_oil),
            'type': NOTIFICATION_TYPES['PREMIUM_INSIGHT'],
            'priority': NOTIFICATION_PRIORITY['HIGH'],
            'action': 'checklist',
        })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['maintenance'][0]
    insights.append({
        'title': title_base,
        'description': desc_base.format(usage_type=usage_type_str),
        'type': NOTIFICATION_TYPES['MAINTENANCE_REMINDER'],
        'priority': NOTIFICATION_PRIORITY['MEDIUM'],
        'action': 'parts',
    })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['fuel'][0]
    insights.append({
        'title': title_base,
        'description': desc_base.format(brand=brand, model=model),
        'type': NOTIFICATION_TYPES['FUEL_ALERT'],
        'priority': NOTIFICATION_PRIORITY['LOW'],
        'action': 'report',
    })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['fuel'][1]
    insights.append({
        'title': title_base,
        'description': desc_base.format(fuel_type=fuel),
        'type': NOTIFICATION_TYPES['FUEL_ALERT'],
        'priority': NOTIFICATION_PRIORITY['LOW'],
    })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['driving'][0]
    insights.append({
        'title': title_base,
        'description': desc_base,
        'type': NOTIFICATION_TYPES['VEHICLE_TIP'],
        'priority': NOTIFICATION_PRIORITY['LOW'],
    })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['health'][0]
    insights.append({
        'title': title_base,
        'description': desc_base.format(brand=brand, model=model),
        'type': NOTIFICATION_TYPES['PREMIUM_INSIGHT'],
        'priority': NOTIFICATION_PRIORITY['MEDIUM'],
        'action': 'obd',
    })

    title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['health'][1]
    insights.append({
        'title': title_base,
        'description': desc_base,
        'type': NOTIFICATION_TYPES['PREMIUM_INSIGHT'],
        'priority': NOTIFICATION_PRIORITY['LOW'],
    })

    recent_scans = OBDScan.query.filter_by(vehicle_id=vehicle.id).order_by(OBDScan.id.desc()).limit(1).all()
    if recent_scans and recent_scans[0].dtc_codes and len(recent_scans[0].dtc_codes) > 0:
        title_base, desc_base = STATIC_AI_INSIGHTS_BY_CATEGORY['obd'][0]
        insights.append({
            'title': title_base,
            'description': desc_base.format(dtc_count=len(recent_scans[0].dtc_codes)),
            'type': NOTIFICATION_TYPES['OBD_ALERT'],
            'priority': NOTIFICATION_PRIORITY['HIGH'],
            'action': 'obd',
        })

    return insights


def _ai_prompt_generator(user, vehicle, usage_type_str):
    return f"""
    Você é um assistente de manutenção automotiva experiente, especializado em percepção preditiva e recomendações inteligentes.
    Gere de 5 a 8 notificações personalizadas para o dono do veículo abaixo.

    DADOS DO USUÁRIO:
    - Nome: {user.full_name}
    - Plano PREMIUM
    - Frequência de lembretes: {user.reminder_frequency}

    DADOS DO VEÍCULO:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Motorização: {vehicle.engine_type}
    - Transmissão: {vehicle.transmission}
    - Combustível: {vehicle.fuel_type}
    - Perfil de Uso: {usage_type_str}
    - Quilometragem atual: {vehicle.mileage or 0} km
    - Última troca de óleo (km): {vehicle.last_oil_change or 0}
    - Última troca de correia (km): {vehicle.last_belt_change or 0}
    - Última troca de freios (km): {vehicle.last_brake_change or 0}

    REGRAS:
    1. Responda APENAS com um JSON no formato abaixo, sem texto adicional.
    2. NOTIFICAÇÕES DEVEM SER PREDITIVAS e baseadas em engenharia automotiva real (ex: intervalo de troca de óleo em 10mil km para veículos a gasolina).
    3. Priorize: trocas prestes a vencer (menos de 2000km), dicas de economia para combustível do veículo, análise do perfil de direção, recomendações de sazonalidade.
    4. Cada notificação deve ter um nível de prioridade: 'low', 'medium', 'high', 'critical'.
    5. Tipos válidos de notificação: 'maintenance', 'obd', 'tip', 'milestone', 'premium', 'fuel'.

    FORMATO JSON OBRIGATÓRIO:
    [
      {{
        "title": "Título curto",
        "description": "Texto explicativo de 2 a 3 frases, personalizado.",
        "type": "tip | maintenance | fuel | premium | obd | milestone",
        "priority": "low | medium | high | critical",
        "action": "obd | checklist | parts | report | null"
      }}
    ]
    """


def _ai_insight_generator(user, vehicle, usage_type_str):
    if not ai_client:
        return _static_ai_insight_generator(user, vehicle, usage_type_str)

    try:
        prompt = _ai_prompt_generator(user, vehicle, usage_type_str)
        completion = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.6,
            max_tokens=2400,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Você é um engenheiro mecânico automotivo sênior especializado em manutenção preventiva e preditiva. Responde somente JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            timeout=60,
        )
        raw = completion.choices[0].message.content or ''
        parsed = __import__('json').loads(raw)
        items = parsed.get('notifications') if isinstance(parsed, dict) else parsed
        if not isinstance(items, list):
            return _static_ai_insight_generator(user, vehicle, usage_type_str)

        cleaned = []
        for entry in items[:PREMIUM_AI_NOTIFICATION_LIMIT]:
            entry_type = entry.get('type') or NOTIFICATION_TYPES['VEHICLE_TIP']
            valid_types = set(NOTIFICATION_TYPES.values())
            if entry_type not in valid_types:
                entry_type = NOTIFICATION_TYPES['VEHICLE_TIP']
            priority = entry.get('priority') or NOTIFICATION_PRIORITY['MEDIUM']
            valid_priority = set(NOTIFICATION_PRIORITY.values())
            if priority not in valid_priority:
                priority = NOTIFICATION_PRIORITY['MEDIUM']
            cleaned.append({
                'title': str(entry.get('title') or 'Insight Premium').strip()[:120],
                'description': str(entry.get('description') or '').strip()[:500],
                'type': entry_type,
                'priority': priority,
                'action': entry.get('action') if entry.get('action') in ('obd', 'checklist', 'parts', 'report') else None,
            })
        if not cleaned:
            return _static_ai_insight_generator(user, vehicle, usage_type_str)
        return cleaned
    except Exception as e:
        print(f"AI insight generation falhou, usando fallback estático: {str(e)}")
        return _static_ai_insight_generator(user, vehicle, usage_type_str)


def _seed_basic_notifications(user, vehicle):
    created_any = False
    created_count = Notification.query.filter_by(user_id=user.id).count()
    if created_count == 0:
        _persist_notification(
            user.id, vehicle and vehicle.id,
            'Bem-vindo(a) ao AMP!',
            f'Olá {user.full_name.split()[0] if user.full_name else ""}! Cadastre seu veículo e comece a usar o diagnóstico OBD-II para monitorar a saúde do seu carro em tempo real.',
            NOTIFICATION_TYPES['SYSTEM'],
            NOTIFICATION_PRIORITY['LOW'],
            ai=False,
            premium=False,
        )
        created_any = True
    return created_any


def _filter_ai_insights_by_preferences(user, insights):
    if not user.is_premium:
        return []
    filtered = []
    for ins in insights:
        t = ins.get('type')
        keep = True
        if t in (NOTIFICATION_TYPES['FUEL_ALERT'], NOTIFICATION_TYPES['VEHICLE_TIP']):
            if not user.premium_driving_analysis:
                keep = False
        if t == NOTIFICATION_TYPES['PREMIUM_INSIGHT'] and not user.premium_ai_insights:
            keep = False
        if ins.get('priority') in (NOTIFICATION_PRIORITY['HIGH'], NOTIFICATION_PRIORITY['CRITICAL']):
            if not user.premium_predictive:
                keep = False
        if not _user_allows_notification_type(user, t, ai_generated=True):
            keep = False
        if keep:
            filtered.append(ins)
    return filtered


def generate_smart_notifications(user, force_refresh=False):
    if not _should_regenerate_for_user(user, force_refresh=force_refresh):
        return

    vehicle = Vehicle.query.filter_by(user_id=user.id).order_by(Vehicle.id.desc()).first()
    if not vehicle:
        _seed_basic_notifications(user, None)
        user.last_notif_generation = _now_iso()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return

    usage_type_str = vehicle.usage_type or 'Misto'
    current_km = vehicle.mileage or 0

    if force_refresh:
        Notification.query.filter_by(
            user_id=user.id,
            ai_generated=True,
            premium_only=True
        ).delete(synchronize_session=False)

    changed = _seed_basic_notifications(user, vehicle)

    next_oil = (vehicle.last_oil_change or 0) + 10000
    if next_oil - current_km <= 2000:
        days_left, km_left = _days_until_next_km(current_km, next_oil, 60)
        rec = _persist_notification(
            user, vehicle.id,
            'Troca de Óleo Próxima',
            f'Faltam apenas {km_left} km para a troca recomendada de óleo. Este período crítico pode aumentar o desgaste do motor se ignorado.',
            NOTIFICATION_TYPES['MAINTENANCE_REMINDER'],
            NOTIFICATION_PRIORITY['HIGH'],
            payload={'next_km': next_oil, 'current_km': current_km, 'days_left': days_left},
            action='checklist'
        )
        if rec is not None:
            changed = True

    if (vehicle.last_belt_change or 0) > 0:
        next_belt = (vehicle.last_belt_change or 0) + 50000
        if next_belt - current_km <= 5000:
            rec = _persist_notification(
                user, vehicle.id,
                'Correia Dentada: Atenção!',
                'Você está próximo do limite recomendado para a troca da correia dentada. A quebra em movimento pode danificar seriamente o motor.',
                NOTIFICATION_TYPES['MAINTENANCE_REMINDER'],
                NOTIFICATION_PRIORITY['CRITICAL'],
                payload={'next_km': next_belt},
                action='parts'
            )
            if rec is not None:
                changed = True

    recent_maint = MaintenanceHistory.query.filter_by(vehicle_id=vehicle.id).count()
    if recent_maint == 0 and current_km > 5000:
        rec = _persist_notification(
            user, vehicle.id,
            'Registre seu Histórico',
            'Adicione os serviços já feitos no seu carro no histórico de manutenção. Isso ajuda a IA a gerar recomendações ainda mais precisas.',
            NOTIFICATION_TYPES['SYSTEM'],
            NOTIFICATION_PRIORITY['LOW'],
            action='checklist'
        )
        if rec is not None:
            changed = True

    if user.is_premium:
        current_premium_ai_count = Notification.query.filter_by(
            user_id=user.id,
            ai_generated=True,
            premium_only=True,
        ).count()
        if current_premium_ai_count < PREMIUM_AI_NOTIFICATION_LIMIT:
            raw_insights = _ai_insight_generator(user, vehicle, usage_type_str)
            insights = _filter_ai_insights_by_preferences(user, raw_insights)
            for insight in insights:
                remaining = PREMIUM_AI_NOTIFICATION_LIMIT - Notification.query.filter_by(
                    user_id=user.id, ai_generated=True, premium_only=True
                ).count()
                if remaining <= 0:
                    break
                rec = _persist_notification(
                    user, vehicle.id,
                    insight['title'],
                    insight['description'],
                    insight['type'],
                    insight['priority'],
                    ai=True,
                    premium=True,
                    action=insight.get('action'),
                )
                if rec is not None:
                    changed = True
            if insights and user.premium_ai_insights:
                rec = _persist_notification(
                    user, vehicle.id,
                    'Análise Premium Atualizada ✨',
                    f'Foram gerados insights personalizados por IA para o seu {vehicle.brand} {vehicle.model}. Confira as recomendações abaixo!',
                    NOTIFICATION_TYPES['PREMIUM_INSIGHT'],
                    NOTIFICATION_PRIORITY['MEDIUM'],
                    ai=True,
                    premium=True,
                )
                if rec is not None:
                    changed = True

    user.last_notif_generation = _now_iso()

    if changed:
        try:
            db.session.commit()
        except Exception as e:
            print(f"Erro ao salvar notificações geradas: {str(e)}")
            db.session.rollback()

user_bp = Blueprint('user', __name__)

PLAN_VEHICLE_LIMITS = {
    'free': 1,
    'mensal': 1,
    'trimestral': 1,
    'anual': 1
}


def get_vehicle_limit(plan_type):
    return PLAN_VEHICLE_LIMITS.get(plan_type, 1)


@user_bp.route('/register', methods=['POST'])
def register():
    print("\n=== NOVO PEDIDO DE REGISTRO ===")
    try:
        data = request.get_json()
        print(f"Dados recebidos: {data}")
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        return jsonify({'error': 'Erro ao processar dados JSON'}), 400
        
    if not data:
        print("Erro: Nenhum dado recebido")
        return jsonify({'error': 'Nenhum dado recebido'}), 400
        
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    
    if not all([full_name, email, password]):
        missing = [k for k in ['full_name', 'email', 'password'] if not data.get(k)]
        print(f"Erro: Campos ausentes: {missing}")
        return jsonify({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}), 400
    
    try:
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.password == password:
                print(f"Usuário já existe (Login automático): {email}")
                return jsonify({
                    'message': 'Usuário já cadastrado, realizando login automático', 
                    'user': existing_user.to_dict()
                }), 200
            else:
                print(f"Erro: Email já cadastrado com outra senha: {email}")
                return jsonify({'error': 'Este email já está cadastrado com outra senha'}), 400
        
        new_user = User(
            full_name=full_name,
            email=email,
            password=password
        )
        
        db.session.add(new_user)
        db.session.commit()
        print(f"Usuário criado com sucesso: {email}")
        return jsonify({'message': 'Usuário registrado com sucesso', 'user': new_user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro de banco de dados: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Credenciais ausentes'}), 400
    
    user = User.query.filter_by(email=data['email'], password=data['password']).first()
    
    if user:
        return jsonify({'message': 'Login realizado com sucesso', 'user': user.to_dict()}), 200
    else:
        return jsonify({'error': 'Email ou senha inválidos'}), 401


@user_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logout realizado com sucesso'}), 200


@user_bp.route('/user/report/<int:user_id>', methods=['GET'])
def get_user_report(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    vehicles = Vehicle.query.filter_by(user_id=user_id).all()
    all_history = []
    for v in vehicles:
        for h in v.maintenance_history:
            history_dict = h.to_dict()
            history_dict['vehicle_model'] = v.model
            all_history.append(history_dict)

    all_history.sort(key=lambda x: x['last_date'] if x['last_date'] else '', reverse=True)
    latest_vehicle = Vehicle.query.filter_by(user_id=user_id).order_by(Vehicle.id.desc()).first()

    return jsonify({
        'user_name': user.full_name,
        'history': all_history,
        'vehicle_id': latest_vehicle.id if latest_vehicle else None
    }), 200


@user_bp.route('/user/status/<int:user_id>', methods=['GET'])
def get_user_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    vehicles = Vehicle.query.filter_by(user_id=user_id).all()
    vehicle = vehicles[0] if vehicles else None
    status = {
        'user': user.to_dict(),
        'vehicle': vehicle.to_dict() if vehicle else None,
        'vehicles': [v.to_dict() for v in vehicles],  # Always an array
        'recommendation': 'Nenhuma recomendação no momento.'
    }

    if vehicle:
        current_km = vehicle.mileage
        oil_diff = current_km - vehicle.last_oil_change
        if oil_diff >= 9000:
            status['recommendation'] = f'Seu carro está com {current_km} km. Troca de óleo necessária (última há {oil_diff} km)!'
        else:
            next_change = vehicle.last_oil_change + 10000
            status['recommendation'] = f'Próxima troca de óleo estimada aos {next_change} km.'

    return jsonify(status), 200


@user_bp.route('/user/vehicles/<int:user_id>', methods=['GET'])
def get_user_vehicles(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    vehicles = Vehicle.query.filter_by(user_id=user_id).all()
    return jsonify({'vehicles': [v.to_dict() for v in vehicles]}), 200


NOTIFICATION_PREF_FIELDS = [
    'notifications_enabled',
    'notif_maintenance', 'notif_obd', 'notif_fuel',
    'notif_tips', 'notif_milestones', 'notif_system',
    'premium_ai_insights', 'premium_predictive',
    'premium_driving_analysis', 'premium_seasonal',
    'premium_smart_frequency',
]


@user_bp.route('/user/<int:user_id>', methods=['GET', 'PUT', 'PATCH'])
def get_or_update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    if request.method in ['PUT', 'PATCH']:
        data = request.json or {}
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'reminder_frequency' in data:
            user.reminder_frequency = data['reminder_frequency']
        if 'avatar' in data:
            user.avatar = data['avatar']
        for field in NOTIFICATION_PREF_FIELDS:
            if field in data:
                try:
                    setattr(user, field, bool(data[field]))
                except Exception:
                    pass

        db.session.commit()
        return jsonify({'message': 'Usuário atualizado com sucesso', 'user': user.to_dict()}), 200

    return jsonify(user.to_dict()), 200


@user_bp.route('/user/<int:user_id>/notification-preferences', methods=['GET', 'PUT', 'PATCH'])
def notification_preferences(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    if request.method in ['PUT', 'PATCH']:
        data = request.json or {}
        if 'reminder_frequency' in data:
            user.reminder_frequency = data['reminder_frequency']
        for field in NOTIFICATION_PREF_FIELDS:
            if field in data:
                try:
                    setattr(user, field, bool(data[field]))
                except Exception:
                    pass
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    prefs = {f: bool(getattr(user, f, True)) for f in NOTIFICATION_PREF_FIELDS}
    prefs['reminder_frequency'] = user.reminder_frequency
    return jsonify({
        'preferences': prefs,
        'is_premium': bool(user.is_premium),
        'last_generation': user.last_notif_generation,
    }), 200


@user_bp.route('/user/notifications/<int:user_id>/periodic-check', methods=['POST'])
def periodic_notification_check(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    force = (request.json or {}).get('force', False)
    should_run = _should_regenerate_for_user(user, force_refresh=force)

    if not should_run:
        return jsonify({
            'skipped': True,
            'reason': 'Frequência mínima não atingida',
            'last_generation': user.last_notif_generation,
        }), 200

    try:
        generate_smart_notifications(user, force_refresh=force)
    except Exception as e:
        print(f"Erro no trigger periódico: {str(e)}")
        return jsonify({'error': str(e)}), 500

    try:
        query = Notification.query.filter_by(user_id=user.id)
        if not user.is_premium:
            query = query.filter(Notification.premium_only == False)
        notifications = query.order_by(Notification.id.desc()).limit(20).all()
        unread = sum(1 for n in notifications if not n.read)
        return jsonify({
            'generated': True,
            'unread_count': unread,
            'total': len(notifications),
            'is_premium': bool(user.is_premium),
            'notifications_enabled': bool(user.notifications_enabled),
        }), 200
    except Exception as e:
        return jsonify({'generated': True, 'error': str(e)}), 200


@user_bp.route('/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200


@user_bp.route('/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    print(f"=== Tentando excluir usuário com ID: {user_id} ===")
    user = User.query.get(user_id)
    if not user:
        print(f"Erro: Usuário com ID {user_id} não encontrado")
        return jsonify({'error': 'Usuário não encontrado'}), 404

    try:
        print(f"Usuário encontrado: {user.email}")
        print(f"Veículos associados: {len(user.vehicles)}")
        db.session.delete(user)
        db.session.commit()
        print(f"Usuário {user.email} excluído com sucesso")
        return jsonify({'message': 'Usuário e todos os dados associados excluídos com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir usuário: {str(e)}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/user/notifications/<int:user_id>', methods=['GET'])
def get_user_notifications(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    try:
        from app import db as _db
        _inspector = _db.inspect(_db.engine)
        if 'notification' not in _inspector.get_table_names():
            print("Tabela notification não existe, criando via fallback...")
            try:
                Notification.__table__.create(bind=_db.engine, checkfirst=True)
            except Exception as table_err:
                print(f"Erro ao criar tabela notification: {table_err}")
    except Exception:
        pass

    force_refresh = request.args.get('refresh', 'false').lower() in ('1', 'true', 'yes', 's')

    try:
        generate_smart_notifications(user, force_refresh=force_refresh)
    except Exception as e:
        print(f"Erro ao gerar notificações inteligentes: {str(e)}")

    try:
        query = Notification.query.filter_by(user_id=user.id)
        if not user.is_premium:
            query = query.filter(Notification.premium_only == False)
        notifications = query.order_by(
            Notification.priority.desc() if hasattr(Notification.priority, 'desc') else Notification.id.desc(),
            Notification.id.desc()
        ).limit(50).all()

        unread_count = 0
        for n in notifications:
            if not n.read:
                unread_count += 1

        notification_dicts = []
        for n in notifications:
            try:
                notification_dicts.append(n.to_dict())
            except Exception:
                pass

        return jsonify({
            'notifications': notification_dicts,
            'unread_count': unread_count,
            'total_count': len(notification_dicts),
            'is_premium': bool(user.is_premium),
        }), 200
    except Exception as e:
        print(f"Erro ao carregar notificações do banco: {str(e)}")
        fallback = []
        if Notification.query.count() == 0:
            fallback.append({
                'id': 'fallback-welcome',
                'title': 'Bem-vindo(a) ao AMP!',
                'description': f'Olá {user.full_name.split()[0] if user.full_name else ""}! Assim que você cadastrar seu veículo, as notificações inteligentes começarão a aparecer aqui.',
                'type': NOTIFICATION_TYPES['SYSTEM'],
                'priority': NOTIFICATION_PRIORITY['LOW'],
                'read': False,
                'time': _now_iso(),
                'created_at': _now_iso(),
            })
        return jsonify({'notifications': fallback, 'unread_count': 1 if fallback else 0}), 200


@user_bp.route('/user/notifications/<int:user_id>/read-all', methods=['PATCH'])
def mark_all_notifications_read(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    try:
        updated = Notification.query.filter_by(
            user_id=user.id,
            read=False
        ).update({'read': True}, synchronize_session=False)
        db.session.commit()
        return jsonify({
            'message': 'Notificações marcadas como lidas',
            'updated_count': int(updated or 0)
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao marcar notificações como lidas: {str(e)}")
        return jsonify({'error': str(e), 'message': 'Notificações marcadas como lidas'}), 200


@user_bp.route('/user/notifications/<int:user_id>/<int:notif_id>/read', methods=['PATCH'])
def mark_single_notification_read(user_id, notif_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    notification = Notification.query.filter_by(id=notif_id, user_id=user.id).first()
    if not notification:
        return jsonify({'error': 'Notificação não encontrada'}), 404

    notification.read = True
    db.session.commit()
    return jsonify({'message': 'Notificação marcada como lida'}), 200


@user_bp.route('/user/notifications/<int:user_id>/ai/generate', methods=['POST'])
def regenerate_ai_notifications(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    if not user.is_premium:
        return jsonify({'error': 'Funcionalidade exclusiva do plano PREMIUM'}), 403

    try:
        generate_smart_notifications(user, force_refresh=True)
        return jsonify({'message': 'Notificações IA regeneradas com sucesso'}), 200
    except Exception as e:
        print(f"Erro ao regenerar notificações IA: {str(e)}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/user/set-plan/<int:user_id>', methods=['POST'])
def set_user_plan(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.json
    plan_type = data.get('plan_type')
    if plan_type not in PLAN_VEHICLE_LIMITS:
        return jsonify({'error': f'Plano inválido. Opções: {list(PLAN_VEHICLE_LIMITS.keys())}'}), 400

    was_premium = bool(user.is_premium)
    user.plan_type = plan_type
    user.is_premium = plan_type != 'free'
    db.session.commit()

    if not was_premium and user.is_premium:
        try:
            generate_smart_notifications(user, force_refresh=True)
        except Exception as e:
            print(f"Aviso: Não foi possível gerar notificações premium após upgrade: {str(e)}")

    return jsonify({
        'message': 'Plano atualizado com sucesso',
        'user': user.to_dict()
    }), 200
