from flask import Blueprint, request, jsonify
from app.models.models import Vehicle, MaintenanceHistory, OBDScan
from app import db
import json
import os

try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=openai_api_key) if openai_api_key and openai_api_key != "your_openai_api_key_here" else None
except ImportError:
    client = None
    print("OpenAI module not available - AI features will use static fallback")

vehicle_bp = Blueprint('vehicle', __name__)

# --- Dados de veículos compatíveis ---
SUPPORTED_BRANDS = {
    'Ford': {
        'models': ['Fiesta', 'Focus', 'Ranger', 'Ka', 'EcoSport', 'Fusion', 'Edge', 'Mustang', 'Territory', 'Bronco'],
        'engines': {
            'Fiesta': ['1.0 Rocam', '1.6 Rocam', '1.0 EcoBoost', '1.5 Sigma'],
            'Focus': ['1.6 Sigma', '2.0 Duratec', '2.0 GDI'],
            'Ranger': ['2.2 Diesel', '3.2 Diesel', '2.5 Flex'],
        },
        'start_year': 2010,
    },
    'Chevrolet': {
        'models': ['Onix', 'Prisma', 'Cruze', 'S10', 'Tracker', 'Spin', 'Montana', 'Equinox', 'Trailblazer', 'Camaro', 'Cobalt', 'Classic', 'Celta'],
        'engines': {
            'Onix': ['1.0 Aspirado', '1.0 Turbo', '1.4 Aspirado'],
        },
        'start_year': 2011,
    },
    'Volkswagen': {
        'models': ['Gol', 'Polo', 'Golf', 'T-Cross', 'Amarok', 'Virtus', 'Nivus', 'Taos', 'Jetta', 'Tiguan', 'Voyage', 'Saveiro', 'Fox', 'CrossFox'],
        'start_year': 2010,
    },
    'Toyota': {
        'models': ['Corolla', 'Hilux', 'Yaris', 'Etios', 'SW4', 'Rav4', 'Camry', 'Prius', 'Corolla Cross', 'Innova', 'Land Cruiser'],
        'start_year': 2012,
    },
    'Hyundai': {
        'models': ['HB20', 'Creta', 'Tucson', 'i30', 'Santa Fe', 'Elantra', 'Sonata', 'Azera', 'HR', 'iX35'],
        'start_year': 2012,
    },
    'Honda': {
        'models': ['Civic', 'Fit', 'City', 'HR-V', 'CR-V', 'Accord', 'WR-V', 'Pilot'],
        'start_year': 2010,
    },
    'Nissan': {
        'models': ['Versa', 'March', 'Kicks', 'Sentra', 'Altima', 'Frontier', 'X-Trail', 'Livina'],
        'start_year': 2012,
    },
    'Renault': {
        'models': ['Sandero', 'Logan', 'Duster', 'Kwid', 'Captur', 'Clio', 'Fluence', 'Oroch'],
        'start_year': 2011,
    },
    'Fiat': {
        'models': ['Uno', 'Palio', 'Argo', 'Cronos', 'Mobi', 'Toro', 'Strada', 'Fiorino', 'Doblo'],
        'start_year': 2010,
    },
    'Jeep': {
        'models': ['Renegade', 'Compass', 'Wrangler', 'Cherokee', 'Grand Cherokee', 'Commander'],
        'start_year': 2015,
    },
    'BMW': {
        'models': ['3 Series', '5 Series', 'X1', 'X3', 'X5', 'X6', '1 Series', '2 Series'],
        'start_year': 2012,
    },
    'Mercedes-Benz': {
        'models': ['C-Class', 'E-Class', 'GLA', 'GLC', 'GLE', 'A-Class', 'CLA'],
        'start_year': 2013,
    },
    'Audi': {
        'models': ['A3', 'A4', 'Q3', 'Q5', 'Q7', 'A1', 'A6'],
        'start_year': 2012,
    },
    'Peugeot': {
        'models': ['208', '308', '2008', '3008', '5008', 'Partner'],
        'start_year': 2014,
    },
    'Citroën': {
        'models': ['C3', 'C4 Cactus', 'Aircross', 'C4 Lounge', 'Jumpy'],
        'start_year': 2013,
    },
}


def validate_and_fix_images(data, key):
    """Garante que não há erros de bloqueio removendo imagens externas."""
    if key in data:
        for item in data[key]:
            item['image_url'] = ''
    return data


@vehicle_bp.route('/vehicle/brands', methods=['GET'])
def get_brands():
    return jsonify(list(SUPPORTED_BRANDS.keys())), 200


@vehicle_bp.route('/vehicle/models/<brand>', methods=['GET'])
def get_models(brand):
    if brand in SUPPORTED_BRANDS:
        return jsonify(SUPPORTED_BRANDS[brand]['models']), 200
    return jsonify({'error': 'Marca não suportada'}), 404


@vehicle_bp.route('/vehicle/engines/<brand>/<model>', methods=['GET'])
def get_engines(brand, model):
    if brand in SUPPORTED_BRANDS:
        brand_data = SUPPORTED_BRANDS[brand]
        if 'engines' in brand_data and model in brand_data['engines']:
            return jsonify(brand_data['engines'][model]), 200
        return jsonify(['1.0', '1.4', '1.6', '1.8', '2.0', '2.0 Turbo']), 200
    return jsonify({'error': 'Marca não suportada'}), 404


@vehicle_bp.route('/vehicle/years/<brand>/<model>', methods=['GET'])
def get_years(brand, model):
    if brand in SUPPORTED_BRANDS:
        brand_data = SUPPORTED_BRANDS[brand]
        current_year = 2026
        start_year = brand_data.get('start_year', 2010)
        if 'model_start_years' in brand_data and model in brand_data['model_start_years']:
            start_year = brand_data['model_start_years'][model]
        years = list(range(current_year, start_year - 1, -1))
        return jsonify(years), 200
    return jsonify({'error': 'Marca não suportada'}), 404


@vehicle_bp.route('/vehicle/<int:vehicle_id>', methods=['GET', 'PUT', 'PATCH'])
def get_or_update_vehicle(vehicle_id):
    if request.method == 'GET':
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            return jsonify({'error': 'Veículo não encontrado'}), 404
        return jsonify(vehicle.to_dict()), 200

    print(f"\n=== ATUALIZANDO VEÍCULO ID: {vehicle_id} ===")
    data = request.json
    print(f"Dados recebidos para atualização: {data}")

    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        print("Erro: Veículo não encontrado no banco")
        return jsonify({'error': 'Veículo não encontrado'}), 404

    try:
        if 'brand' in data:
            if not data['brand'] or str(data['brand']).strip() == '':
                return jsonify({'error': 'Marca não pode ser vazia'}), 400
            if data['brand'] not in SUPPORTED_BRANDS:
                return jsonify({'error': 'Marca não compatível com OBD-II Bluetooth'}), 400
            vehicle.brand = data['brand']

        effective_brand = data.get('brand') if 'brand' in data else vehicle.brand

        if 'model' in data:
            if not data['model'] or str(data['model']).strip() == '':
                return jsonify({'error': 'Modelo não pode ser vazio'}), 400
            brand_data = SUPPORTED_BRANDS.get(effective_brand)
            if brand_data and data['model'] not in brand_data.get('models', []):
                return jsonify({'error': 'Modelo não compatível com OBD-II Bluetooth'}), 400
            vehicle.model = data['model']

        effective_model = data.get('model') if 'model' in data else vehicle.model

        if 'year' in data:
            if data['year'] is None or data['year'] == '' or (isinstance(data['year'], float) and data['year'] != int(data['year'])):
                return jsonify({'error': 'Ano inválido'}), 400
            try:
                year_value = int(data['year'])
            except (TypeError, ValueError):
                return jsonify({'error': 'Ano inválido'}), 400
            brand_data = SUPPORTED_BRANDS.get(effective_brand, {})
            model_start_year = brand_data.get('model_start_years', {}).get(
                effective_model, brand_data.get('start_year', 2010)
            )
            current_year = 2026
            if year_value < model_start_year or year_value > current_year:
                return jsonify({
                    'error': f'Ano {year_value} não é válido para {effective_brand} {effective_model}. '
                             f'Anos disponíveis: {model_start_year} - {current_year}'
                }), 400
            vehicle.year = year_value

        if 'engine_type' in data and data.get('engine_type'):
            brand_data = SUPPORTED_BRANDS.get(effective_brand, {})
            valid_engines = brand_data.get('engines', {}).get(effective_model, [])
            if valid_engines and data['engine_type'] not in valid_engines:
                return jsonify({
                    'error': f'Motorização {data["engine_type"]} não é válida para {effective_brand} {effective_model}. '
                             f'Opções válidas: {", ".join(valid_engines)}'
                }), 400
            vehicle.engine_type = data['engine_type']

        if 'mileage' in data:
            if data['mileage'] is None or data['mileage'] == '':
                vehicle.mileage = 0
            else:
                try:
                    vehicle.mileage = int(data['mileage'])
                except (TypeError, ValueError):
                    return jsonify({'error': 'Quilometragem inválida'}), 400

        if 'last_oil_change' in data:
            if data['last_oil_change'] is None or data['last_oil_change'] == '':
                vehicle.last_oil_change = 0
            else:
                try:
                    vehicle.last_oil_change = int(data['last_oil_change'])
                except (TypeError, ValueError):
                    return jsonify({'error': 'Última troca de óleo inválida'}), 400

        if 'last_belt_change' in data:
            if data['last_belt_change'] is None or data['last_belt_change'] == '':
                vehicle.last_belt_change = 0
            else:
                try:
                    vehicle.last_belt_change = int(data['last_belt_change'])
                except (TypeError, ValueError):
                    return jsonify({'error': 'Última troca de correia inválida'}), 400

        if 'last_brake_change' in data:
            if data['last_brake_change'] is None or data['last_brake_change'] == '':
                vehicle.last_brake_change = 0
            else:
                try:
                    vehicle.last_brake_change = int(data['last_brake_change'])
                except (TypeError, ValueError):
                    return jsonify({'error': 'Última troca de freios inválida'}), 400

        if 'transmission' in data:
            vehicle.transmission = data['transmission']
        if 'fuel_type' in data:
            vehicle.fuel_type = data['fuel_type']
        if 'usage_type' in data:
            vehicle.usage_type = data['usage_type']

        db.session.commit()
        print("Veículo atualizado com sucesso!")
        return jsonify({
            'message': 'Veículo atualizado com sucesso',
            'vehicle': vehicle.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar veículo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@vehicle_bp.route('/vehicle/register', methods=['POST'])
def register_vehicle():
    data = request.json
    if not data or not all(k in data for k in ('brand', 'model', 'year', 'user_id')):
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400

    from app.models.models import User
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    PLAN_VEHICLE_LIMITS = {'free': 1, 'mensal': 1, 'trimestral': 1, 'anual': 1}
    current_vehicle_count = Vehicle.query.filter_by(user_id=user.id).count()
    vehicle_limit = PLAN_VEHICLE_LIMITS.get(user.plan_type, 1)

    if current_vehicle_count >= vehicle_limit:
        return jsonify({
            'error': f'Limite de veículos atingido para o plano "{user.plan_type or "free"}". Máximo permitido: {vehicle_limit}.',
            'limit_reached': True,
            'current_count': current_vehicle_count,
            'limit': vehicle_limit
        }), 403

    new_vehicle = Vehicle(
        brand=data['brand'],
        model=data['model'],
        year=data['year'],
        transmission=data.get('transmission'),
        mileage=data.get('mileage', 0),
        fuel_type=data.get('fuel_type'),
        engine_type=data.get('engine_type'),
        usage_type=data.get('usage_type'),
        user_id=data['user_id'],
        last_oil_change=data.get('last_oil_change', 0),
        last_belt_change=data.get('last_belt_change', 0),
        last_brake_change=data.get('last_brake_change', 0)
    )

    try:
        db.session.add(new_vehicle)
        db.session.commit()
        return jsonify({'message': 'Veículo registrado com sucesso', 'vehicle': new_vehicle.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@vehicle_bp.route('/vehicle/maintenance', methods=['POST'])
def save_maintenance():
    print("\n=== NOVO REGISTRO DE MANUTENÇÃO ===")
    data = request.json
    print(f"Dados recebidos: {data}")
    
    if not data or not data.get('vehicle_id') or not data.get('history'):
        print("Erro: Dados obrigatórios ausentes")
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
    
    try:
        vehicle_id = data['vehicle_id']
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            print(f"Erro: Veículo ID {vehicle_id} não encontrado no banco")
            vehicle = Vehicle.query.first()
            if not vehicle:
                return jsonify({'error': 'Nenhum veículo cadastrado no sistema'}), 404
            vehicle_id = vehicle.id
            print(f"Usando fallback para Veículo ID: {vehicle_id}")

        for entry in data['history']:
            print(f"Processando entrada: {entry}")
            new_entry = MaintenanceHistory(
                vehicle_id=vehicle_id,
                item=entry['item'],
                last_km=entry.get('last_km', 0),
                last_date=entry.get('last_date'),
                cost=float(entry.get('cost', 0.0)),
                liters=float(entry.get('liters', 0.0))
            )
            db.session.add(new_entry)
        
        db.session.commit()
        print("Registro salvo com sucesso!")
        return jsonify({'message': 'Histórico de manutenção salvo com sucesso'}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar no banco: {str(e)}")
        return jsonify({'error': str(e)}), 500


@vehicle_bp.route('/vehicle/maintenance/<int:maintenance_id>', methods=['DELETE'])
def delete_maintenance(maintenance_id):
    print(f"\n=== EXCLUINDO REGISTRO DE MANUTENÇÃO ID: {maintenance_id} ===")
    try:
        entry = MaintenanceHistory.query.get(maintenance_id)
        if not entry:
            return jsonify({'error': 'Registro não encontrado'}), 404
            
        db.session.delete(entry)
        db.session.commit()
        print("Registro excluído com sucesso!")
        return jsonify({'message': 'Registro excluído com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir: {str(e)}")
        return jsonify({'error': str(e)}), 500


@vehicle_bp.route('/vehicle/maintenance/<int:maintenance_id>', methods=['PUT', 'PATCH'])
def update_maintenance(maintenance_id):
    print(f"\n=== ATUALIZANDO MANUTENÇÃO ID: {maintenance_id} ===")
    data = request.json
    entry = MaintenanceHistory.query.get(maintenance_id)
    if not entry:
        return jsonify({'error': 'Registro não encontrado'}), 404

    try:
        if 'last_date' in data:
            entry.last_date = data['last_date']
        if 'cost' in data:
            entry.cost = float(data['cost'])
        if 'liters' in data:
            entry.liters = float(data['liters'])
        if 'item' in data:
            entry.item = data['item']

        db.session.commit()
        print("Registro atualizado com sucesso!")
        return jsonify({'message': 'Registro atualizado com sucesso', 'entry': entry.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar: {str(e)}")
        return jsonify({'error': str(e)}), 500


def get_static_checklist(vehicle):
    current_km = vehicle.mileage
    checklist = []
    item_id = 1

    oil_diff = current_km - vehicle.last_oil_change
    if oil_diff >= 9000:
        checklist.append({
            'id': item_id,
            'name': 'Troca de Óleo e Filtro de Óleo',
            'description': f'Já se passaram {oil_diff}km desde a última troca.',
            'reason': 'O óleo perde a viscosidade e capacidade de lubrificação com o tempo/uso, podendo fundir o motor.',
            'priority': 'URGENTE' if oil_diff >= 10000 else 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id += 1

    belt_diff = current_km - vehicle.last_belt_change
    if belt_diff >= 50000:
        checklist.append({
            'id': item_id,
            'name': 'Troca de Correia Dentada (ou Inspeção de Corrente)',
            'description': f'Já se passaram {belt_diff}km desde a última troca/inspeção.',
            'reason': 'Quebra da correia pode causar danos catastróficos no motor (valvas batendo nos pistões).',
            'priority': 'URGENTE' if belt_diff >= 60000 else 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id += 1

    brake_diff = current_km - vehicle.last_brake_change
    if brake_diff >= 30000:
        checklist.append({
            'id': item_id,
            'name': 'Troca de Pastilhas de Freio (ou Inspeção)',
            'description': f'Já se passaram {brake_diff}km desde a última troca.',
            'reason': 'Pastilhas desgastadas aumentam a distância de frenagem e danificam os discos.',
            'priority': 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id += 1

    # Add additional standard checks
    checklist.append({
        'id': item_id,
        'name': 'Inspeção do Filtro de Ar',
        'description': 'Verificar e limpar/trocar o filtro de ar do motor.',
        'reason': 'Filtro de ar sujo reduz a performance e aumenta o consumo de combustível.',
        'priority': 'PRÓXIMOS 30 DIAS',
        'image_url': ''
    })
    item_id += 1

    checklist.append({
        'id': item_id,
        'name': 'Verificação do Líquido de Arrefecimento',
        'description': 'Checar o nível e a condição do líquido de arrefecimento.',
        'reason': 'Baixo nível ou líquido contaminado pode causar superaquecimento do motor.',
        'priority': 'PRÓXIMOS 60 DIAS',
        'image_url': ''
    })
    item_id += 1

    checklist.append({
        'id': item_id,
        'name': 'Inspeção dos Pneus e Calibragem',
        'description': 'Verificar o desgaste dos pneus e calibrar a pressão correta.',
        'reason': 'Pneus mal calibrados ou desgastados aumentam o consumo e o risco de acidentes.',
        'priority': 'PRÓXIMOS 30 DIAS',
        'image_url': ''
    })
    item_id += 1

    checklist.append({
        'id': item_id,
        'name': 'Verificação dos Fluidos (Freio, Direção, Câmbio)',
        'description': 'Checar o nível dos fluidos de freio, direção hidráulica e câmbio.',
        'reason': 'Baixo nível de fluido pode comprometer o funcionamento seguro do veículo.',
        'priority': 'PRÓXIMOS 60 DIAS',
        'image_url': ''
    })
    item_id += 1

    checklist.append({
        'id': item_id,
        'name': 'Inspeção das Luzes (Faróis, Lanternas, Setas)',
        'description': 'Verificar se todas as luzes do veículo estão funcionando corretamente.',
        'reason': 'Luzes quebradas comprometem a visibilidade e a segurança no trânsito.',
        'priority': 'PRÓXIMOS 90 DIAS',
        'image_url': ''
    })

    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model}",
        'mileage': current_km,
        'checklist': checklist
    }), 200


@vehicle_bp.route('/vehicle/checklist/<int:vehicle_id>', methods=['GET'])
def get_vehicle_checklist(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
    return get_static_checklist(vehicle)


@vehicle_bp.route('/vehicle/checklist/ai/<int:vehicle_id>', methods=['GET'])
def get_vehicle_checklist_ai(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404

    if not client:
        print("OpenAI API Key missing. Falling back to static checklist.")
        return get_static_checklist(vehicle)

    prompt = f"""
    Como um engenheiro mecânico automotivo sênior, gere um CHECKLIST DE MANUTENÇÃO PREVENTIVA ESPECÍFICO para o veículo abaixo.

    Dados do veículo:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Transmissão: {vehicle.transmission}
    - Motorização: {vehicle.engine_type}
    - Combustível: {vehicle.fuel_type}
    - Quilometragem atual: {vehicle.mileage} km
    - Última troca de óleo: {vehicle.last_oil_change} km
    - Última troca de correia dentada: {vehicle.last_belt_change} km
    - Última troca de freios: {vehicle.last_brake_change} km

    Instruções:
    1. Gere de 5 a 10 itens de manutenção preventiva específicos para este veículo
    2. Cada item deve ter:
       - Nome claro e direto
       - Descrição detalhada do que precisa ser feito
       - Razão para fazer a manutenção (risco de não fazer)
       - Prioridade (URGENTE, PRÓXIMOS 30 DIAS, PRÓXIMOS 60 DIAS, PRÓXIMOS 90 DIAS)
    3. Priorize itens com base na quilometragem atual e nas últimas manutenções
    4. Use linguagem clara e acessível

    Retorne APENAS um JSON no seguinte formato:
    {{
        "checklist": [
            {{
                "id": 1,
                "name": "Nome do item",
                "description": "Descrição detalhada",
                "reason": "Risco de não fazer",
                "priority": "PRIORIDADE_AQUI",
                "image_url": ""
            }}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um mecânico sênior especialista em manutenção preventiva."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)

        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model}",
            'mileage': vehicle.mileage,
            'checklist': ai_data['checklist']
        }), 200
    except Exception as e:
        print(f"AI Checklist Error: {str(e)}. Falling back to static data.")
        return get_static_checklist(vehicle)


def get_static_maintenance_tips(vehicle):
    """Static fallback maintenance tips."""
    tips = [
        {
            'id': 1,
            'title': 'Óleo do motor',
            'content': 'Verifique o nível do óleo a cada 15 dias ou antes de viagens longas. Observe nível, viscosidade e cor. Troque entre 5.000 e 10.000 km, conforme o tipo do óleo e o manual do carro.'
        },
        {
            'id': 2,
            'title': 'Fluidos essenciais',
            'content': 'Cheque fluido de freio, direção hidráulica, embreagem (se houver), arrefecimento e limpador de para-brisa. Todos devem estar no nível correto.'
        },
        {
            'id': 3,
            'title': 'Calibragem dos pneus',
            'content': 'Faça semanalmente com pneus frios. Pressões ideais estão no manual ou na porta do motorista.'
        },
        {
            'id': 4,
            'title': 'Pastilhas e discos de freio',
            'content': 'Ruídos ao frear, vibração no pedal ou aumento da distância de frenagem indicam desgaste.'
        },
        {
            'id': 5,
            'title': f'Câmbio {vehicle.transmission or ""}',
            'content': 'Verifique vazamentos e dificuldade de engate — pode indicar desgaste no kit embreagem (para câmbio manual).'
        },
        {
            'id': 6,
            'title': 'Lavagem e enceramento',
            'content': 'Reduzem corrosão e protegem a pintura.'
        }
    ]

    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year})",
        'tips': tips
    }), 200


@vehicle_bp.route('/vehicle/maintenance-tips/<int:vehicle_id>', methods=['GET'])
def get_maintenance_tips(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404

    if not client:
        print("OpenAI API Key missing. Falling back to static maintenance tips.")
        return get_static_maintenance_tips(vehicle)

    prompt = f"""
    Como um engenheiro mecânico automotivo sênior, gere uma lista de DICAS DE MANUTENÇÃO PREVENTIVA ESPECÍFICAS para o veículo abaixo.

    Dados do veículo:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Transmissão: {vehicle.transmission}
    - Motorização: {vehicle.engine_type}
    - Combustível: {vehicle.fuel_type}

    Instruções:
    1. Gere de 8 a 12 dicas práticas e úteis para o dia a dia do usuário
    2. Cada dica deve ser específica para este veículo, não genérica
    3. As dicas devem cobrir diferentes aspectos: inspeções simples, cuidados diários, economias de combustível, etc.
    4. Use linguagem clara e acessível

    Retorne APENAS um JSON no seguinte formato:
    {{
        "tips": [
            {{
                "id": 1,
                "title": "Título curto da dica",
                "content": "Conteúdo detalhado da dica, com explicações claras"
            }}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um mecânico sênior especialista em manutenção preventiva."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)

        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year})",
            'tips': ai_data['tips']
        }), 200
    except Exception as e:
        print(f"AI Maintenance Tips Error: {str(e)}. Falling back to static data.")
        return get_static_maintenance_tips(vehicle)


@vehicle_bp.route('/vehicle/parts/<int:vehicle_id>', methods=['GET'])
def get_vehicle_parts(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
    
    transmission_type = vehicle.transmission.lower() if vehicle.transmission else 'manual'
    is_automatic = 'autom' in transmission_type
    
    parts_catalog = [
        {
            'id': 1,
            'name': 'Filtro de Óleo',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': f'Filtra as impurezas do óleo. Se não trocado, o óleo sujo causa atrito excessivo e pode danificar o motor {vehicle.engine_type}.',
            'details': {
                'purpose': 'Manter a pureza do lubrificante para proteger bronzinas e pistões.',
                'location': 'Parte inferior do motor, próximo ao cárter.',
                'common_problems': 'Luz de óleo piscando ou ruídos metálicos no motor.',
                'maintenance_interval': '10.000km ou 1 ano'
            },
            'image_url': ''
        },
        {
            'id': 2,
            'name': 'Filtro de Ar do Motor',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Filtra impurezas do ar que entra no motor. Filtro sujo reduz a potência e aumenta o consumo.',
            'details': {
                'purpose': 'Garantir ar limpo para a combustão eficiente.',
                'location': 'Caixa de filtro de ar, geralmente no canto superior do motor.',
                'common_problems': 'Perda de potência, aumento do consumo, dificuldade de partida.',
                'maintenance_interval': '10.000 a 15.000km'
            },
            'image_url': ''
        },
        {
            'id': 3,
            'name': 'Filtro de Combustível',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Filtra impurezas do combustível antes de chegar ao injetor ou carburador.',
            'details': {
                'purpose': 'Proteger o sistema de injeção ou carburador de sujeiras.',
                'location': 'Na linha de combustível, próximo ao tanque ou ao motor.',
                'common_problems': 'Dificuldade de partida, falhas na aceleração, aumento do consumo.',
                'maintenance_interval': '20.000 a 30.000km'
            },
            'image_url': ''
        },
        {
            'id': 4,
            'name': 'Filtro de Cabine (Ar Condicionado)',
            'category': 'Filtros',
            'subcategory': 'Conforto',
            'description': 'Filtra o ar que entra no interior do veículo, removendo poeira e poluentes.',
            'details': {
                'purpose': 'Garantir ar limpo para os ocupantes do veículo.',
                'location': 'Geralmente abaixo do painel ou no capô, próximo à entrada de ar.',
                'common_problems': 'Mau cheiro no ar-condicionado, redução da vazão de ar.',
                'maintenance_interval': '15.000 a 20.000km'
            },
            'image_url': ''
        },
        {
            'id': 5,
            'name': 'Pastilhas de Freio (Dianteiras)',
            'category': 'Freios',
            'subcategory': 'Segurança',
            'description': 'Componentes que aplicam atrito nos discos de freio para parar o veículo.',
            'details': {
                'purpose': 'Garantir a parada segura do veículo.',
                'location': 'Nas pinças de freio, junto aos discos.',
                'common_problems': 'Barulho de raspagem, aumento da distância de frenagem.',
                'maintenance_interval': '20.000 a 40.000km'
            },
            'image_url': ''
        },
        {
            'id': 6,
            'name': 'Pastilhas de Freio (Traseiras)',
            'category': 'Freios',
            'subcategory': 'Segurança',
            'description': 'Componentes de freio traseiro, muitas vezes menores que as dianteiras.',
            'details': {
                'purpose': 'Auxiliar na parada segura e equilibrada do veículo.',
                'location': 'Nas pinças ou tambores de freio traseiros.',
                'common_problems': 'Barulho de raspagem, desgaste irregular.',
                'maintenance_interval': '30.000 a 50.000km'
            },
            'image_url': ''
        },
        {
            'id': 7,
            'name': 'Fluído de Freio',
            'category': 'Fluidos',
            'subcategory': 'Segurança',
            'description': 'Fluído que transmite a força do pedal aos freios. Absorve umidade com o tempo.',
            'details': {
                'purpose': 'Garantir a transmissão eficiente da força de freio.',
                'location': 'Reservatório no compartimento do motor e circuito hidráulico.',
                'common_problems': 'Pedal de freio "frouxo", redução da eficácia de frenagem.',
                'maintenance_interval': '2 anos ou 40.000km'
            },
            'image_url': ''
        },
        {
            'id': 8,
            'name': 'Líquido de Arrefecimento',
            'category': 'Fluidos',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Fluído que mantém a temperatura do motor dentro do ideal.',
            'details': {
                'purpose': 'Evitar superaquecimento e congelamento do motor.',
                'location': 'Radiador, mangueiras e reservatório de expansão.',
                'common_problems': 'Superaquecimento, vazamentos, ferrugem no sistema.',
                'maintenance_interval': '2 a 4 anos ou 40.000 a 80.000km'
            },
            'image_url': ''
        },
        {
            'id': 9,
            'name': 'Óleo do Câmbio',
            'category': 'Fluidos',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Lubrifica as engrenagens do câmbio, garantindo trocas suaves.',
            'details': {
                'purpose': 'Proteger as engrenagens e garantir trocas de marcha suaves.',
                'location': 'Câmbio do veículo.',
                'common_problems': 'Dificuldade em trocar marchas, ruídos no câmbio, vazamentos.',
                'maintenance_interval': '40.000 a 80.000km (varia por tipo de câmbio)'
            },
            'image_url': ''
        },
        {
            'id': 10,
            'name': 'Velas de Ignição',
            'category': 'Ignição',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Produz a centelha que ignita a mistura ar-combustível no motor.',
            'details': {
                'purpose': 'Garantir a combustão eficiente no motor.',
                'location': 'No cabeçote do motor, uma por cilindro.',
                'common_problems': 'Dificuldade de partida, falhas na aceleração, aumento do consumo.',
                'maintenance_interval': '30.000 a 60.000km (varia por tipo de vela)'
            },
            'image_url': ''
        }
    ]
    
    # Add transmission-specific parts
    if is_automatic:
        parts_catalog.extend([
            {
                'id': 11,
                'name': 'Filtro do Câmbio Automático',
                'category': 'Câmbio',
                'subcategory': 'Manutenção Preventiva',
                'description': 'Filtra impurezas do óleo do câmbio automático para proteger componentes internos.',
                'details': {
                    'purpose': 'Manter o óleo do câmbio limpo para prolongar a vida útil.',
                    'location': 'Dentro ou próximo ao cárter do câmbio automático.',
                    'common_problems': 'Trocas de marcha lentas ou bruscas, patinação do câmbio.',
                    'maintenance_interval': '40.000 a 60.000km'
                },
                'image_url': ''
            }
        ])
    else:
        parts_catalog.extend([
            {
                'id': 11,
                'name': 'Kit de Embreagem',
                'category': 'Câmbio',
                'subcategory': 'Manutenção Preventiva',
                'description': 'Conjunto de disco, platô e rolamento que permite trocar marchas.',
                'details': {
                    'purpose': 'Permitir a conexão e desconexão do motor com o câmbio.',
                    'location': 'Entre o motor e o câmbio manual.',
                    'common_problems': 'Dificuldade em trocar marchas, cheiro de queimado, patinação.',
                    'maintenance_interval': '80.000 a 150.000km (varia por uso)'
                },
                'image_url': ''
            }
        ])
    
    # Check for timing belt or chain
    engine_str = (vehicle.engine_type or '').lower()
    if 'fire' in engine_str or 'e.torq' in engine_str or 'flex' in engine_str:
        parts_catalog.append({
            'id': 12,
            'name': 'Corrente de Distribuição',
            'category': 'Motor',
            'subcategory': 'Inspeção',
            'description': 'Componente que sincroniza a rotação do virabrequim e do cabeçote.',
            'details': {
                'purpose': 'Garantir o sincronismo correto das valvas e pistões.',
                'location': 'Interna ao motor, necessita de inspeção periódica.',
                'common_problems': 'Ruído de "plástico" no motor, vibrações.',
                'maintenance_interval': 'Inspeção a cada 60.000km'
            },
            'image_url': ''
        })
    else:
        parts_catalog.append({
            'id': 12,
            'name': 'Correia Dentada',
            'category': 'Motor',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Correia que sincroniza a rotação do virabrequim e do cabeçote, crítica para evitar danos graves.',
            'details': {
                'purpose': 'Garantir o sincronismo correto para evitar danos no motor.',
                'location': 'Externa ou interna ao motor, com proteção.',
                'common_problems': 'Quebra repentina (causa danos graves), rachaduras na correia.',
                'maintenance_interval': '50.000 a 80.000km'
            },
            'image_url': ''
        })
    
    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year}) - {vehicle.transmission} - {vehicle.engine_type}",
        'parts': parts_catalog
    }), 200


@vehicle_bp.route('/vehicle/parts/ai/<int:vehicle_id>', methods=['GET'])
def get_vehicle_parts_ai(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404

    if not client:
        print("OpenAI API Key missing. Falling back to static parts catalog.")
        return get_vehicle_parts(vehicle_id)

    prompt = f"""
    Como um engenheiro mecânico automotivo sênior especialista em manutenção preventiva, gere um catálogo focado EXCLUSIVAMENTE em PEÇAS DE MANUTENÇÃO para o veículo abaixo. O objetivo é ajudar o usuário a entender a função de cada peça e a importância de trocá-la preventivamente para evitar danos maiores.

    Dados específicos do veículo:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Motorização: {vehicle.engine_type}
    - Transmissão: {vehicle.transmission}
    - Combustível: {vehicle.fuel_type}
    - Perfil de Uso: {vehicle.usage_type}

    Categorias válidas para usar:
    - Filtros
    - Freios
    - Fluidos
    - Ignição
    - Câmbio
    - Motor
    - Conforto
    - Segurança

    Instruções críticas:
    1. Seja específico para este veículo exato:
       - Verifique se o motor usa CORRENTE DE DISTRIBUIÇÃO ou CORREIA DENTADA
       - Ajuste todos os itens para o motor, ano e modelo exatos
       - Não inclua peças que não existem ou não são necessárias para este veículo
    2. Se o motor usa corrente de distribuição:
       - Substitua "Correia Dentada" por "Corrente de Distribuição"
       - Inclua "Guias da Corrente de Distribuição"
       - Inclua "Tensor da Corrente de Distribuição"
       - Marque esses itens como "Inspecção" em vez de troca periódica obrigatória
    3. Gere de 8 a 15 peças relevantes para manutenção preventiva deste veículo
    4. Para cada peça, use uma das categorias válidas listadas acima

    Retorne APENAS um JSON no formato:
    {{
        "parts": [
            {{
                "id": 1,
                "name": "Nome da Peça de Manutenção",
                "category": "Uma das categorias válidas",
                "subcategory": "Tipo de manutenção (Preventiva/Inspecção)",
                "description": "Explicação clara da função e o risco de não realizar a manutenção para este veículo",
                "image_url": "",
                "details": {{
                    "purpose": "Finalidade técnica no contexto deste veículo",
                    "location": "Onde se encontra no carro",
                    "common_problems": "Sinais de que a peça está falhando",
                    "maintenance_interval": "Intervalo recomendado"
                }}
            }}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um engenheiro mecânico sênior especialista em catálogo de peças automotivas."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        # Ensure all parts have valid categories and subcategories
        for part in ai_data.get('parts', []):
            if 'category' not in part or not part['category']:
                part['category'] = 'Geral'
            if 'subcategory' not in part or not part['subcategory']:
                part['subcategory'] = 'Manutenção Preventiva'
        
        ai_data = validate_and_fix_images(ai_data, 'parts')
        
        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year}) - {vehicle.transmission} - {vehicle.engine_type}",
            'parts': ai_data['parts']
        }), 200
    except Exception as e:
        print(f"AI Parts Error: {str(e)}. Falling back to static data.")
        return get_vehicle_parts(vehicle_id)


# OBD Scan Routes
@vehicle_bp.route('/vehicle/obd-scans/<int:vehicle_id>', methods=['GET'])
def get_obd_scans(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
    
    scans = OBDScan.query.filter_by(vehicle_id=vehicle_id).order_by(OBDScan.scan_date.desc()).all()
    
    return jsonify({
        'vehicle': vehicle.to_dict(),
        'scans': [scan.to_dict() for scan in scans]
    }), 200


@vehicle_bp.route('/vehicle/obd-scan', methods=['POST'])
def save_obd_scan():
    from datetime import datetime
    
    print("\n=== NOVO SCAN OBD ===")
    data = request.json
    print(f"Dados recebidos: {data}")
    
    if not data or not data.get('vehicle_id'):
        print("Erro: Dados obrigatórios ausentes")
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
    
    try:
        vehicle_id = data['vehicle_id']
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            print(f"Erro: Veículo ID {vehicle_id} não encontrado no banco")
            return jsonify({'error': 'Veículo não encontrado'}), 404
        
        new_scan = OBDScan(
            vehicle_id=vehicle_id,
            scan_date=data.get('scan_date', datetime.now().isoformat()),
            dtc_codes=data.get('dtc_codes', []),
            live_data=data.get('live_data', {}),
            connected_device=data.get('connected_device')
        )
        
        db.session.add(new_scan)
        db.session.commit()
        print("Scan salvo com sucesso!")
        
        return jsonify({
            'message': 'Scan OBD salvo com sucesso',
            'scan': new_scan.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar scan: {str(e)}")
        return jsonify({'error': str(e)}), 500


@vehicle_bp.route('/vehicle/obd-scan/analyze/<int:scan_id>', methods=['GET'])
def analyze_obd_scan(scan_id):
    scan = OBDScan.query.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan não encontrado'}), 404
    
    vehicle = Vehicle.query.get(scan.vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
    
    if not client:
        print("OpenAI API Key missing. Falling back to static analysis.")
        return jsonify({
            'analysis': 'Análise AI não disponível sem chave OpenAI.',
            'recommendations': []
        }), 200
    
    previous_scans = OBDScan.query.filter(
        OBDScan.vehicle_id == vehicle.id,
        OBDScan.id != scan_id
    ).order_by(OBDScan.scan_date.desc()).limit(5).all()
    
    prompt = f"""
    Você é um mecânico automotivo sênior especializado em diagnóstico OBD-II.
    Analise o scan OBD abaixo e forneça insights claros e práticos.

    Dados do veículo:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Motorização: {vehicle.engine_type}
    - Quilometragem atual: {vehicle.mileage} km

    Scan atual:
    - Data: {scan.scan_date}
    - Códigos de erro (DTC): {scan.dtc_codes}
    - Dados em tempo real: {scan.live_data}
    - Dispositivo conectado: {scan.connected_device}

    Scans anteriores (últimos 5): {[s.to_dict() for s in previous_scans]}

    Instruções:
    1. Analise cada código de erro (se houver) e explique o que significa e qual é o risco
    2. Verifique os dados em tempo real (como RPM, temperatura, nível de combustível, pressão do coletor, etc.) para identificar valores anômalos
    3. Compare com os scans anteriores para ver padrões (como códigos que aparecem repetidamente)
    4. Forneça recomendações práticas de manutenção preventiva ou reparo
    5. Mencione o que deve ser melhorado em termos de acompanhamento do veículo

    Retorne APENAS um JSON no seguinte formato:
    {{
        "analysis": "Texto principal da análise, com explicações claras",
        "recommendations": [
            {{
                "priority": "alta", "média" ou "baixa",
                "title": "Título da recomendação",
                "description": "Explicação detalhada da recomendação"
            }}
        ],
        "abnormal_values": [
            {{
                "parameter": "Nome do parâmetro",
                "current_value": "Valor atual",
                "expected_range": "Intervalo esperado",
                "issue": "Qual é o problema"
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Você é um mecânico automotivo sênior especializado em diagnóstico OBD-II."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        return jsonify(ai_data), 200
    except Exception as e:
        print(f"AI Analysis Error: {str(e)}. Falling back to static analysis.")
        return jsonify({
            'analysis': 'Não foi possível gerar análise AI no momento.',
            'recommendations': [],
            'abnormal_values': []
        }), 200
