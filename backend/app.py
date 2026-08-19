from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    client = None
    print("OpenAI module not available - AI features will use static fallback")

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'amp_db.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Import models
from app.models.models import User, Vehicle, MaintenanceHistory, OBDScan

# Plan Vehicle Limits
PLAN_VEHICLE_LIMITS = {
    'free': 1,
    'mensal': 1,
    'trimestral': 1,
    'anual': 1
}

def get_vehicle_limit(plan_type):
    return PLAN_VEHICLE_LIMITS.get(plan_type, 1)  # fallback seguro: 1 veículo

# Predefined "Supported" Vehicle Data (OBD-II Bluetooth + API/Doc compatible)
SUPPORTED_BRANDS = {
    'Ford': {
        'models': ['Fiesta', 'Focus', 'Ranger', 'Ka', 'EcoSport', 'Fusion', 'Edge', 'Mustang', 'Territory', 'Bronco'],
        'engines': {
            'Fiesta': ['1.0 Rocam', '1.6 Rocam', '1.0 EcoBoost', '1.5 Sigma'],
            'Focus': ['1.6 Sigma', '2.0 Duratec', '2.0 GDI'],
            'Ranger': ['2.2 Diesel', '3.2 Diesel', '2.5 Flex'],
            'Ka': ['1.0 Rocam', '1.5 Sigma'],
            'EcoSport': ['1.5 Sigma', '1.6 Rocam', '2.0 Duratec', '1.0 EcoBoost'],
            'Fusion': ['2.0 Duratec', '2.0 EcoBoost', '2.5 Hybrid'],
            'Edge': ['2.0 EcoBoost', '3.5 V6'],
            'Mustang': ['2.3 EcoBoost', '5.0 V8'],
            'Territory': ['1.5 EcoBoost', '2.0 EcoBoost'],
            'Bronco': ['2.0 EcoBoost', '2.3 EcoBoost', '2.7 V6 EcoBoost']
        },
        'start_year': 2010,
        'docs': 'Ford Developer API / OpenXC'
    },
    'Chevrolet': {
        'models': ['Onix', 'Prisma', 'Cruze', 'S10', 'Tracker', 'Spin', 'Montana', 'Equinox', 'Trailblazer', 'Camaro'],
        'engines': {
            'Onix': ['1.0 Aspirado', '1.0 Turbo', '1.4 Aspirado'],
            'S10': ['2.4 Flex', '2.5 Flex', '2.8 Diesel'],
            'Prisma': ['1.0 Aspirado', '1.4 Aspirado'],
            'Cruze': ['1.4 Turbo', '1.8 Aspirado', '2.0 Diesel'],
            'Tracker': ['1.0 Turbo', '1.2 Turbo', '1.4 Turbo'],
            'Spin': ['1.8 Aspirado', '1.8 Flex'],
            'Montana': ['1.4 Aspirado', '1.8 Aspirado'],
            'Equinox': ['1.5 Turbo', '2.0 Turbo'],
            'Trailblazer': ['2.8 Diesel', '3.6 V6'],
            'Camaro': ['2.0 Turbo', '3.6 V6', '6.2 V8']
        },
        'start_year': 2011,
        'docs': 'GM Developer Portal'
    },
    'Volkswagen': {
        'models': ['Gol', 'Polo', 'Golf', 'T-Cross', 'Amarok', 'Virtus', 'Nivus', 'Taos', 'Jetta', 'Tiguan', 'Voyage', 'Saveiro'],
        'engines': {
            'Polo': ['1.0 MPI', '1.6 MSI', '1.0 TSI (200 TSI)', '1.4 TSI (GTS)'],
            'Golf': ['1.4 TSI', '2.0 TSI (GTI)', '1.6 MSI'],
            'T-Cross': ['1.0 TSI (200 TSI)', '1.4 TSI (250 TSI)'],
            'Gol': ['1.0 MPI', '1.6 MSI', '1.0 TSI'],
            'Amarok': ['2.0 Diesel', '3.0 V6 Diesel'],
            'Virtus': ['1.0 MPI', '1.6 MSI', '1.0 TSI'],
            'Nivus': ['1.0 TSI (200 TSI)', '1.4 TSI'],
            'Taos': ['1.4 TSI', '2.0 TSI'],
            'Jetta': ['1.4 TSI', '2.0 TSI', '2.0 Diesel'],
            'Tiguan': ['1.4 TSI', '2.0 TSI'],
            'Voyage': ['1.0 MPI', '1.6 MSI'],
            'Saveiro': ['1.6 MSI']
        },
        'start_year': 2010,
        'docs': 'VW Car-Net API'
    },
    'Toyota': {
        'models': ['Corolla', 'Hilux', 'Yaris', 'Etios', 'SW4', 'Rav4', 'Camry', 'Prius', 'Corolla Cross'],
        'engines': {
            'Corolla': ['1.8 Hybrid', '2.0 Dynamic Force', '1.8 Dual VVT-i', '2.0 Dual VVT-i'],
            'Hilux': ['2.7 Flex', '2.8 Diesel', '3.0 Diesel'],
            'Yaris': ['1.3 Dual VVT-i', '1.5 Dual VVT-i'],
            'Etios': ['1.3 Dual VVT-i', '1.5 Dual VVT-i'],
            'SW4': ['2.7 Flex', '2.8 Diesel', '4.0 V6'],
            'Rav4': ['2.0 Dynamic Force', '2.5 Hybrid'],
            'Camry': ['2.5 Hybrid', '3.5 V6'],
            'Prius': ['1.8 Hybrid'],
            'Corolla Cross': ['1.8 Hybrid', '2.0 Dynamic Force']
        },
        'start_year': 2012,
        'docs': 'Toyota Connected Services API'
    },
    'Honda': {
        'models': ['Civic', 'Fit', 'City', 'HR-V', 'CR-V', 'WR-V', 'Accord'],
        'engines': {
            'Civic': ['2.0 i-VTEC', '1.5 Turbo', '1.8 i-VTEC'],
            'HR-V': ['1.8 i-VTEC', '1.5 Turbo'],
            'Fit': ['1.3 i-VTEC', '1.5 i-VTEC'],
            'City': ['1.5 i-VTEC'],
            'CR-V': ['1.5 Turbo', '2.0 i-VTEC', '2.0 Hybrid'],
            'WR-V': ['1.5 i-VTEC'],
            'Accord': ['1.5 Turbo', '2.0 Hybrid', '2.0 Turbo']
        },
        'start_year': 2012,
        'docs': 'Honda Developer Studio'
    },
    'Hyundai': {
        'models': ['HB20', 'Creta', 'Tucson', 'i30', 'Santa Fe', 'Azera', 'Elantra', 'Ix35'],
        'engines': {
            'HB20': ['1.0 Aspirado', '1.0 Turbo (TGDI)', '1.6 Aspirado'],
            'Creta': ['1.6 Aspirado', '2.0 Aspirado', '1.0 Turbo (TGDI)', '2.0 Smartstream'],
            'i30': ['1.6 Gamma', '2.0 Nu', '1.6 Turbo GDI', '1.8 Nu'],
            'Tucson': ['1.6 Turbo GDI', '2.0 Nu', '2.0 Diesel', '1.6 Hybrid'],
            'Santa Fe': ['2.0 Turbo GDI', '2.2 Diesel', '3.5 V6'],
            'Azera': ['3.0 V6', '3.3 V6'],
            'Elantra': ['1.6 Gamma', '2.0 Nu', '1.6 Turbo'],
            'Ix35': ['2.0 Nu', '2.4 Theta II', '2.0 Diesel']
        },
        'start_year': 2012,
        'docs': 'Hyundai Bluelink API'
    },
    'Fiat': {
        'models': ['Uno', 'Palio', 'Argo', 'Cronos', 'Toro', 'Mobi', 'Strada', 'Fastback', 'Pulse', 'Fiorino', 'Siena'],
        'engines': {
            'Pulse': ['1.3 Firefly', '1.0 Turbo 200', '1.3 Turbo 270 (Abarth)'],
            'Fastback': ['1.0 Turbo 200', '1.3 Turbo 270'],
            'Argo': ['1.0 Firefly', '1.3 Firefly', '1.8 E.torQ'],
            'Cronos': ['1.3 Firefly', '1.8 E.torQ'],
            'Toro': ['1.8 E.torQ', '2.4 Tigershark', '2.0 Diesel', '1.3 Turbo 270'],
            'Strada': ['1.4 Fire', '1.6 E.torQ'],
            'Mobi': ['1.0 Fire'],
            'Uno': ['1.0 Fire', '1.3 Firefly'],
            'Palio': ['1.0 Fire', '1.4 Fire', '1.6 E.torQ'],
            'Fiorino': ['1.4 Fire'],
            'Siena': ['1.4 Fire', '1.6 E.torQ']
        },
        'model_start_years': {
            'Pulse': 2021,
            'Fastback': 2022,
            'Argo': 2017,
            'Cronos': 2018,
            'Mobi': 2016,
            'Toro': 2016,
            'Strada': 2010
        },
        'start_year': 2010,
        'docs': 'FCA Developer Portal'
    },
    'Renault': {
        'models': ['Sandero', 'Logan', 'Duster', 'Kwid', 'Oroch', 'Captur', 'Master', 'Stepway'],
        'engines': {
            'Duster': ['1.6 SCe', '2.0 Hi-Flex', '1.3 Turbo TCe'],
            'Sandero': ['1.0 SCe', '1.6 SCe', '2.0 (R.S.)'],
            'Logan': ['1.0 SCe', '1.6 SCe'],
            'Kwid': ['1.0 SCe'],
            'Oroch': ['1.6 SCe', '2.0 Hi-Flex'],
            'Captur': ['1.3 Turbo TCe', '1.6 SCe'],
            'Master': ['2.3 Diesel']
        },
        'start_year': 2012,
        'docs': 'Renault Connected Services'
    },
    'Jeep': {
        'models': ['Renegade', 'Compass', 'Commander', 'Wrangler', 'Cherokee'],
        'engines': {
            'Renegade': ['1.8 E.torQ', '2.0 Diesel', '1.3 Turbo 270'],
            'Compass': ['2.0 Flex', '2.0 Diesel', '1.3 Turbo 270', '1.3 Turbo Hybrid (4xe)'],
            'Commander': ['1.3 Turbo 270', '2.0 Diesel'],
            'Wrangler': ['2.0 Turbo', '3.6 V6', '2.0 Diesel'],
            'Cherokee': ['2.4 Tigershark', '2.0 Turbo', '3.2 V6']
        },
        'start_year': 2015,
        'docs': 'FCA Developer Portal'
    },
    'Nissan': {
        'models': ['March', 'Versa', 'Kicks', 'Frontier', 'Sentra', 'Leaf'],
        'engines': {
            'Kicks': ['1.6 16V Flex'],
            'Frontier': ['2.3 Diesel Turbo', '2.3 Diesel Bi-Turbo', '2.5 Diesel'],
            'March': ['1.0 12V', '1.6 16V'],
            'Versa': ['1.0 12V', '1.6 16V'],
            'Sentra': ['2.0 16V', '1.6 Turbo'],
            'Leaf': ['Elétrico']
        },
        'start_year': 2012,
        'docs': 'Nissan Connect API'
    },
    'Mitsubishi': {
        'models': ['L200', 'Pajero', 'ASX', 'Eclipse Cross', 'Outlander'],
        'engines': {
            'L200': ['2.4 Diesel', '3.2 Diesel', '3.5 Flex'],
            'ASX': ['2.0 MIVEC Flex'],
            'Pajero': ['3.2 Diesel', '3.8 V6'],
            'Eclipse Cross': ['1.5 Turbo', '2.4 Hybrid'],
            'Outlander': ['2.4 MIVEC', '2.4 Hybrid']
        },
        'start_year': 2010,
        'docs': 'Mitsubishi Motors API'
    },
    'Peugeot': {
        'models': ['208', '2008', '3008', '5008', 'Partner', 'Expert'],
        'engines': {
            '208': ['1.2 PureTech', '1.6 Flex', '1.0 Firefly'],
            '3008': ['1.6 THP', '2.0 Diesel', '1.2 PureTech'],
            '2008': ['1.2 PureTech', '1.6 THP'],
            '5008': ['1.2 PureTech', '1.6 THP', '2.0 Diesel'],
            'Partner': ['1.6 HDi', '1.6 THP'],
            'Expert': ['2.0 Diesel']
        },
        'start_year': 2015,
        'docs': 'PSA Group API'
    },
    'Citroën': {
        'models': ['C3', 'C4 Cactus', 'C4 Lounge', 'Berlingo', 'Jumpy'],
        'engines': {
            'C3': ['1.2 PureTech', '1.6 Flex', '1.0 Firefly'],
            'C4 Cactus': ['1.6 Flex', '1.6 THP'],
            'C4 Lounge': ['1.6 THP', '2.0 Diesel'],
            'Berlingo': ['1.6 HDi'],
            'Jumpy': ['2.0 Diesel']
        },
        'start_year': 2015,
        'docs': 'PSA Group API'
    },
    'BMW': {
        'models': ['Série 3', 'Série 1', 'X1', 'X3', 'X5', 'Série 5'],
        'engines': {
            'Série 3': ['2.0 Turbo (320i)', '3.0 Turbo (M340i)', '2.0 Hybrid (330e)'],
            'Série 1': ['1.5 Turbo', '2.0 Turbo'],
            'X1': ['1.5 Turbo', '2.0 Turbo'],
            'X3': ['2.0 Turbo', '3.0 Turbo'],
            'X5': ['3.0 Turbo', '4.4 V8 Turbo'],
            'Série 5': ['2.0 Turbo', '3.0 Turbo', '3.0 Hybrid']
        },
        'start_year': 2014,
        'docs': 'BMW ConnectedDrive API'
    },
    'Mercedes-Benz': {
        'models': ['Classe A', 'Classe C', 'GLA', 'GLC', 'GLE', 'Classe E'],
        'engines': {
            'Classe C': ['1.5 Turbo', '1.6 Turbo', '2.0 Turbo'],
            'Classe A': ['1.3 Turbo', '2.0 Turbo'],
            'GLA': ['1.3 Turbo', '2.0 Turbo'],
            'GLC': ['2.0 Turbo', '3.0 Turbo'],
            'GLE': ['2.0 Turbo', '3.0 Turbo', '3.0 Diesel'],
            'Classe E': ['1.5 Turbo', '2.0 Turbo', '3.0 Turbo']
        },
        'start_year': 2014,
        'docs': 'Mercedes-Benz Developers'
    },
    'Audi': {
        'models': ['A3', 'A4', 'Q3', 'Q5', 'A5', 'Q7'],
        'engines': {
            'A3': ['1.4 TFSI', '2.0 TFSI'],
            'Q3': ['1.4 TFSI', '2.0 TFSI'],
            'A4': ['2.0 TFSI', '3.0 TFSI'],
            'Q5': ['2.0 TFSI', '3.0 TFSI'],
            'A5': ['2.0 TFSI', '3.0 TFSI'],
            'Q7': ['3.0 TFSI', '3.0 TDI']
        },
        'start_year': 2014,
        'docs': 'Audi API Portal'
    },
    'Kia': {
        'models': ['Sportage', 'Cerato', 'Sorento', 'Rio', 'Picanto', 'Stonic', 'Niro'],
        'engines': {
            'Sportage': ['2.0 Flex', '1.6 Turbo Hybrid'],
            'Cerato': ['1.6 Flex', '2.0 Flex'],
            'Sorento': ['2.2 Diesel', '2.5 Turbo'],
            'Rio': ['1.0 MPI', '1.6 MPI'],
            'Picanto': ['1.0 MPI'],
            'Stonic': ['1.0 MPI', '1.0 Turbo'],
            'Niro': ['1.6 Hybrid', '1.6 Plug-in Hybrid']
        },
        'start_year': 2012,
        'docs': 'Kia Connect API'
    },
    'Chery': {
        'models': ['Tiggo 2', 'Tiggo 5X', 'Tiggo 7', 'Tiggo 8', 'Arrizo 5', 'Arrizo 6'],
        'engines': {
            'Tiggo 5X': ['1.5 Turbo Flex'],
            'Tiggo 8': ['1.6 Turbo GDI'],
            'Tiggo 2': ['1.5 Aspirado', '1.5 Turbo'],
            'Tiggo 7': ['1.5 Turbo', '1.6 Turbo GDI'],
            'Arrizo 5': ['1.5 Aspirado'],
            'Arrizo 6': ['1.5 Turbo']
        },
        'start_year': 2018,
        'docs': 'Caoa Chery API'
    }
}

# Create database and tables
def create_tables():
    with app.app_context():
        # Ensure tables are created with new columns
        db.create_all()

# Initial table creation
create_tables()

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'message': 'AMP Backend API is running',
        'status': 'ok'
    }), 200

@app.route('/vehicle/brands', methods=['GET'])
def get_brands():
    return jsonify(list(SUPPORTED_BRANDS.keys())), 200

@app.route('/vehicle/models/<brand>', methods=['GET'])
def get_models(brand):
    if brand in SUPPORTED_BRANDS:
        return jsonify(SUPPORTED_BRANDS[brand]['models']), 200
    return jsonify({'error': 'Marca não suportada'}), 404

@app.route('/vehicle/engines/<brand>/<model>', methods=['GET'])
def get_engines(brand, model):
    if brand in SUPPORTED_BRANDS:
        brand_data = SUPPORTED_BRANDS[brand]
        if 'engines' in brand_data and model in brand_data['engines']:
            return jsonify(brand_data['engines'][model]), 200
        # If no specific engines found for model, return a default list
        return jsonify(['1.0', '1.4', '1.6', '1.8', '2.0', '2.0 Turbo']), 200
    return jsonify({'error': 'Marca não suportada'}), 404

@app.route('/vehicle/years/<brand>/<model>', methods=['GET'])
def get_years(brand, model):
    if brand in SUPPORTED_BRANDS:
        brand_data = SUPPORTED_BRANDS[brand]
        current_year = 2026
        
        # Check for specific model start year
        start_year = brand_data.get('start_year', 2010)
        if 'model_start_years' in brand_data and model in brand_data['model_start_years']:
            start_year = brand_data['model_start_years'][model]
            
        years = list(range(current_year, start_year - 1, -1))
        return jsonify(years), 200
    return jsonify({'error': 'Marca não suportada'}), 404

@app.route('/vehicle/<int:vehicle_id>', methods=['GET', 'PUT', 'PATCH'])
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


@app.route('/vehicle/register', methods=['POST'])
def register_vehicle():
    data = request.json
    if not data or not all(k in data for k in ('brand', 'model', 'year', 'user_id')):
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
    
    # --- VALIDAÇÃO: limite de veículos por plano ---
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    current_vehicle_count = Vehicle.query.filter_by(user_id=user.id).count()
    vehicle_limit = get_vehicle_limit(user.plan_type)

    if current_vehicle_count >= vehicle_limit:
        return jsonify({
            'error': f'Limite de veículos atingido para o plano "{user.plan_type or "free"}". '
                     f'Máximo permitido: {vehicle_limit}. Faça upgrade do plano para cadastrar mais veículos.',
            'limit_reached': True,
            'current_count': current_vehicle_count,
            'limit': vehicle_limit
        }), 403
    
    # Validação: apenas veículos compatíveis com OBD-II Bluetooth
    if data['brand'] not in SUPPORTED_BRANDS:
        return jsonify({'error': 'Marca não compatível com OBD-II Bluetooth'}), 400
    
    brand_data = SUPPORTED_BRANDS[data['brand']]
    if data['model'] not in brand_data['models']:
        return jsonify({'error': 'Modelo não compatível com OBD-II Bluetooth'}), 400
    
    # Validação de ano
    model_start_year = brand_data.get('model_start_years', {}).get(data['model'], brand_data.get('start_year', 2010))
    current_year = 2026
    if data['year'] < model_start_year or data['year'] > current_year:
        return jsonify({'error': f'Ano {data["year"]} não é válido para {data["brand"]} {data["model"]}. Anos disponíveis: {model_start_year} - {current_year}'}), 400
    
    # Validação de motorização
    if data.get('engine_type'):
        valid_engines = brand_data['engines'].get(data['model'], [])
        if valid_engines and data['engine_type'] not in valid_engines:
            return jsonify({'error': f'Motorização {data["engine_type"]} não é válida para {data["brand"]} {data["model"]}. Opções válidas: {", ".join(valid_engines)}'}), 400
    
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

@app.route('/vehicle/obd-scan', methods=['POST'])
def save_obd_scan():
    try:
        data = request.get_json()
        required_fields = ['vehicle_id', 'scan_date']
        if not data or not all(field in data for field in required_fields):
            return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
        
        # Verify vehicle exists
        vehicle = Vehicle.query.get(data['vehicle_id'])
        if not vehicle:
            return jsonify({'error': 'Veículo não encontrado'}), 404
        
        # Create new scan
        new_scan = OBDScan(
            vehicle_id=data['vehicle_id'],
            scan_date=data['scan_date'],
            dtc_codes=data.get('dtc_codes', []),
            live_data=data.get('live_data', {}),
            connected_device=data.get('connected_device')
        )
        
        db.session.add(new_scan)
        db.session.commit()
        return jsonify({'message': 'Scan OBD salvo com sucesso', 'scan': new_scan.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        print('Erro ao salvar scan OBD:', str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/vehicle/checklist/<int:vehicle_id>', methods=['GET'])
def get_vehicle_checklist(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
        
    current_km = vehicle.mileage
    checklist = []
    item_id = 1
    
    # 1. Troca de Óleo e Filtro de Óleo (Geralmente a cada 10.000km)
    oil_diff = current_km - vehicle.last_oil_change
    if oil_diff >= 9000: # Alerta com 1000km de antecedência
        checklist.append({
            'id': item_id,
            'name': 'Troca de Óleo e Filtro de Óleo',
            'description': f'Já se passaram {oil_diff}km desde a última troca.',
            'reason': 'O óleo perde a viscosidade e capacidade de lubrificação com o tempo/uso, podendo fundir o motor.',
            'priority': 'URGENTE' if oil_diff >= 10000 else 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 2. Filtro de Ar do Motor (a cada 10.000-15.000km)
    if oil_diff >= 9000:
        checklist.append({
            'id': item_id,
            'name': 'Filtro de Ar do Motor',
            'description': 'Recomendado trocar junto com o óleo para manter desempenho ideal.',
            'reason': 'Filtro sujo aumenta o consumo de combustível e diminui o desempenho do motor.',
            'priority': 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 3. Filtro de Cabine (Ar-condicionado) (a cada 15.000km ou 1 ano)
    if current_km >= 15000:
        checklist.append({
            'id': item_id,
            'name': 'Filtro de Cabine (Ar-condicionado)',
            'description': 'Verificar e trocar se necessário para manter a qualidade do ar interno.',
            'reason': 'Filtro de cabine sujo pode causar alergias, mau cheiro e reduzir a eficiência do ar-condicionado.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 4. Correia Dentada / Corrente de Distribuição (Depende do motor)
    belt_diff = current_km - vehicle.last_belt_change
    engine_type = vehicle.engine_type
    
    # Verifica se motor usa corrente de distribuição (ex: 1.8 E.torQ)
    uses_timing_chain = 'E.torQ' in engine_type or 'Firefly' in engine_type or '1.8' in engine_type
    
    if uses_timing_chain:
        checklist.append({
            'id': item_id,
            'name': 'Inspecção da Corrente de Distribuição',
            'description': f'Verificar tensão da corrente e condição dos componentes, já que o veículo tem {current_km}km.',
            'reason': 'Corrente desgastada pode causar ruído e desalinhamento no sincronismo do motor.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
        checklist.append({
            'id': item_id,
            'name': 'Inspecção dos Guias da Corrente',
            'description': 'Verificar desgaste nos guias da corrente de distribuição.',
            'reason': 'Guias desgastadas podem causar ruído e diminuir a vida útil da corrente.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
        checklist.append({
            'id': item_id,
            'name': 'Inspecção do Tensor da Corrente',
            'description': 'Verificar se o tensor está mantendo a tensão correta na corrente.',
            'reason': 'Tensor defeituoso pode causar ruído e desgaste excessivo na corrente.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
    else:
        if belt_diff >= 45000:
            checklist.append({
                'id': item_id,
                'name': 'Correia Dentada e Tensor',
                'description': f'Seu carro rodou {belt_diff}km com a correia atual. Recomenda-se troca preventiva.',
                'reason': 'A quebra da correia causa o atropelamento de válvulas, um dano gravíssimo e caro no cabeçote.',
                'priority': 'URGENTE' if belt_diff >= 55000 else 'PRÓXIMOS 60 DIAS',
                'image_url': ''
            })
            item_id +=1
    
    # 5. Correia de Acessórios (Poly-V) (a cada 60.000km ou 4 anos)
    if current_km >= 50000:
        checklist.append({
            'id': item_id,
            'name': 'Correia de Acessórios (Poly-V)',
            'description': 'Verificar estado da correia e trocar se houver rachaduras ou desgaste excessivo.',
            'reason': 'Se a correia quebrar, o alternador, bomba d\'água e compressor do ar-condicionado param de funcionar.',
            'priority': 'PRÓXIMOS 90 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 6. Pastilhas de Freio (Geralmente a cada 20.000-30.000km)
    brake_diff = current_km - vehicle.last_brake_change
    if brake_diff >= 18000:
        checklist.append({
            'id': item_id,
            'name': 'Pastilhas de Freio Dianteiras e Traseiras',
            'description': f'Última revisão de freios foi há {brake_diff}km. Verificar desgaste das pastilhas.',
            'reason': 'Pastilhas gastas perdem eficiência de frenagem, aumentam a distância de parada e podem danificar os discos de freio.',
            'priority': 'URGENTE' if brake_diff >= 25000 else 'PRÓXIMOS 30 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 7. Fluido de Freio (a cada 2 anos)
    if current_km >= 20000:
        checklist.append({
            'id': item_id,
            'name': 'Fluido de Freio',
            'description': 'Verificar nível e qualidade do fluido de freio. Recomenda-se troca a cada 2 anos.',
            'reason': 'Fluido de freio absorve umidade com o tempo, o que reduz a eficiência da frenagem e pode causar falha no sistema.',
            'priority': 'PRÓXIMOS 90 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 8. Líquido de Arrefecimento (a cada 30.000-40.000km)
    if current_km >= 30000:
        checklist.append({
            'id': item_id,
            'name': 'Líquido de Arrefecimento',
            'description': 'Verificar nível, estado e concentração do líquido de arrefecimento.',
            'reason': 'Evita oxidação interna, superaquecimento do motor e danos ao radiador e bomba d\'água.',
            'priority': 'PRÓXIMOS 90 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 9. Velas de Ignição (a cada 40.000-60.000km)
    if current_km >= 35000:
        checklist.append({
            'id': item_id,
            'name': 'Velas de Ignição',
            'description': 'Verificar estado das velas e trocar se necessário para manter eficiência do motor.',
            'reason': 'Velas gastas causam dificuldade de partida, aumento de consumo, perda de desempenho e vibrações.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 10. Amortecedores e Suspensão (inspeção a cada 40.000km)
    if current_km >= 40000:
        checklist.append({
            'id': item_id,
            'name': 'Amortecedores e Sistema de Suspensão',
            'description': 'Inspeção visual de amortecedores, coxins, buchas, pivôs e terminais de direção.',
            'reason': 'Componentes da suspensão desgastados comprometem a estabilidade, dirigibilidade e aumentam o desgaste dos pneus.',
            'priority': 'PRÓXIMOS 60 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 11. Bateria (verificação a cada 6 meses)
    if current_km >= 10000:
        checklist.append({
            'id': item_id,
            'name': 'Bateria e Sistema Elétrico',
            'description': 'Verificar estado da bateria, terminais, alternador e motor de partida.',
            'reason': 'Bateria fraca pode causar dificuldade de partida ou deixar o usuário na rua sem aviso prévio.',
            'priority': 'PRÓXIMOS 90 DIAS',
            'image_url': ''
        })
        item_id +=1
    
    # 12. Pneus (rodízio e balanceamento a cada 10.000km)
    checklist.append({
        'id': item_id,
        'name': 'Pneus: Rodízio, Balanceamento e Alinhamento',
        'description': 'Realizar rodízio dos pneus para uniformizar o desgaste, balanceamento e verificação do alinhamento.',
        'reason': 'Pneus com desgaste irregular reduzem a vida útil, comprometem a segurança e aumentam o consumo de combustível.',
        'priority': 'PRÓXIMOS 30 DIAS' if current_km % 10000 < 2000 else 'PRÓXIMOS 60 DIAS',
        'image_url': ''
    })

    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model}",
        'mileage': current_km,
        'checklist': checklist
    }), 200

@app.route('/vehicle/maintenance', methods=['POST'])
def save_maintenance():
    print("\n=== NOVO REGISTRO DE MANUTENÇÃO ===")
    data = request.json
    print(f"Dados recebidos: {data}")
    
    if not data or not data.get('vehicle_id') or not data.get('history'):
        print("Erro: Dados obrigatórios ausentes")
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
    
    try:
        vehicle_id = data['vehicle_id']
        # Verificar se o veículo existe
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            print(f"Erro: Veículo ID {vehicle_id} não encontrado no banco")
            # Fallback: se não achar, tentar pegar o primeiro veículo do sistema para não dar erro 500
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

@app.route('/vehicle/maintenance/<int:maintenance_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def get_update_delete_maintenance(maintenance_id):
    # First find the maintenance entry
    maintenance_entry = MaintenanceHistory.query.get(maintenance_id)
    if not maintenance_entry:
        return jsonify({'error': 'Registro de manutenção não encontrado'}), 404

    if request.method == 'GET':
        # Return the single entry
        return jsonify(maintenance_entry.to_dict()), 200

    if request.method == 'DELETE':
        try:
            db.session.delete(maintenance_entry)
            db.session.commit()
            return jsonify({'message': 'Registro de manutenção excluído com sucesso'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao excluir registro: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # PUT/PATCH request
    data = request.json
    try:
        if 'item' in data:
            maintenance_entry.item = data['item']
        if 'last_km' in data:
            maintenance_entry.last_km = data['last_km']
        if 'last_date' in data:
            maintenance_entry.last_date = data['last_date']
        if 'cost' in data:
            maintenance_entry.cost = float(data['cost'])
        if 'liters' in data:
            maintenance_entry.liters = float(data['liters'])
        
        db.session.commit()
        return jsonify({
            'message': 'Registro de manutenção atualizado com sucesso',
            'maintenance': maintenance_entry.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar registro: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/user/report/<int:user_id>', methods=['GET'])
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
            
    # Sort history by date (simplified, assuming YYYY-MM-DD or similar)
    all_history.sort(key=lambda x: x['last_date'] if x['last_date'] else '', reverse=True)
    
    # Get the latest vehicle ID to facilitate adding new costs from the report screen
    latest_vehicle = Vehicle.query.filter_by(user_id=user_id).order_by(Vehicle.id.desc()).first()
    
    return jsonify({
        'user_name': user.full_name,
        'history': all_history,
        'vehicle_id': latest_vehicle.id if latest_vehicle else None
    }), 200

@app.route('/user/status/<int:user_id>', methods=['GET'])
def get_user_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    vehicle = Vehicle.query.filter_by(user_id=user_id).order_by(Vehicle.id.desc()).first()
    
    status = {
        'user': user.to_dict(),
        'vehicle': vehicle.to_dict() if vehicle else None,
        'recommendation': "Nenhuma recomendação no momento."
    }
    
    if vehicle:
        current_km = vehicle.mileage
        
        # Lógica baseada no novo campo last_oil_change
        oil_diff = current_km - vehicle.last_oil_change
        if oil_diff >= 9000:
            status['recommendation'] = f"Seu carro está com {current_km} km. Troca de óleo necessária (última há {oil_diff} km)!"
        else:
            next_change = vehicle.last_oil_change + 10000
            status['recommendation'] = f"Próxima troca de óleo estimada aos {next_change} km."
            
        # Prioridade para Correia Dentada se estiver crítica
        belt_diff = current_km - vehicle.last_belt_change
        if belt_diff >= 45000:
            status['recommendation'] = f"ALERTA CRÍTICO: Correia dentada rodou {belt_diff} km. Troque agora para evitar danos!"

    return jsonify(status), 200

@app.route('/user/vehicles/<int:user_id>', methods=['GET'])
def get_user_vehicles(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    vehicles = Vehicle.query.filter_by(user_id=user_id).all()
    return jsonify({'vehicles': [v.to_dict() for v in vehicles]}), 200

@app.route('/user/<int:user_id>', methods=['GET', 'PUT', 'PATCH'])
def get_or_update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    if request.method in ['PUT', 'PATCH']:
        data = request.json
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

        db.session.commit()
        return jsonify({'message': 'Usuário atualizado com sucesso', 'user': user.to_dict()}), 200

    # GET request
    return jsonify(user.to_dict()), 200

@app.route('/user/<int:user_id>', methods=['DELETE'])
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
        return jsonify({'message': 'Usuário excluído com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir usuário: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200

@app.route('/user/activate-premium/<int:user_id>', methods=['POST'])
def activate_premium(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    user.is_premium = True
    db.session.commit()
    
    return jsonify({
        'message': 'Premium ativado com sucesso',
        'user': user.to_dict()
    }), 200

@app.route('/user/set-plan/<int:user_id>', methods=['POST'])
def set_user_plan(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.json
    plan_type = data.get('plan_type')

    if plan_type not in PLAN_VEHICLE_LIMITS:
        return jsonify({'error': f'Plano inválido. Opções: {list(PLAN_VEHICLE_LIMITS.keys())}'}), 400

    user.plan_type = plan_type
    user.is_premium = plan_type != 'free'
    db.session.commit()

    return jsonify({
        'message': 'Plano atualizado com sucesso',
        'user': user.to_dict()
    }), 200

@app.route('/user/change-password/<int:user_id>', methods=['PUT'])
def change_password(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    data = request.json
    
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'error': 'Campos obrigatórios ausentes'}), 400
    
    if user.password != data['current_password']:
        return jsonify({'error': 'Senha atual incorreta'}), 400
    
    if user.password == data['new_password']:
        return jsonify({'error': 'Nova senha deve ser diferente da senha atual'}), 400
    
    user.password = data['new_password']
    db.session.commit()
    
    return jsonify({'message': 'Senha alterada com sucesso'}), 200

@app.route('/user/recover-password', methods=['POST'])
def recover_password():
    data = request.json
    
    if not data or not data.get('email'):
        return jsonify({'error': 'Email é obrigatório'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user:
        # Sempre retorna a mesma mensagem por segurança, para não revelar se o email existe ou não
        return jsonify({'message': 'Se este email estiver cadastrado, você receberá um link de recuperação de senha'}), 200
    
    # Aqui você poderia integrar com um serviço de envio de e-mails como SendGrid ou SMTP
    print(f"[SIMULAÇÃO] Enviando email de recuperação para {user.email}")
    
    return jsonify({'message': 'Se este email estiver cadastrado, você receberá um link de recuperação de senha'}), 200

# --- Reminder Frequency Endpoints ---
@app.route('/user/<int:user_id>/reminder-frequency', methods=['GET'])
def get_reminder_frequency(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    return jsonify({'frequency': user.reminder_frequency}), 200

@app.route('/user/<int:user_id>/reminder-frequency', methods=['PUT'])
def update_reminder_frequency(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    data = request.json
    if 'frequency' not in data:
        return jsonify({'error': 'Campo frequency obrigatório'}), 400
    user.reminder_frequency = data['frequency']
    db.session.commit()
    return jsonify({'message': 'Frequência atualizada com sucesso', 'frequency': user.reminder_frequency}), 200

# --- Notification Endpoints ---
@app.route('/user/notifications/<int:user_id>', methods=['GET'])
def get_user_notifications(user_id):
    # Return a dummy list of notifications for now
    notifications = [
        {
            "id": 1,
            "title": "Bem-vindo!",
            "message": "Obrigado por usar o nosso app!",
            "read": False,
            "created_at": "2026-07-09"
        }
    ]
    return jsonify({'notifications': notifications}), 200

@app.route('/user/notifications/mark-read/<int:user_id>', methods=['POST'])
def mark_notifications_read(user_id):
    # Dummy endpoint to mark notifications as read
    return jsonify({'message': 'Notificações marcadas como lidas'}), 200

# --- AI Powered Endpoints ---

def validate_and_fix_images(data, key):
    """Garante que não há erros de bloqueio removendo imagens externas."""
    if key in data:
        for item in data[key]:
            item['image_url'] = ""
    return data

@app.route('/vehicle/parts/ai/<int:vehicle_id>', methods=['GET'])
def get_vehicle_parts_ai(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404

    # Check if API Key is configured
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("OpenAI API Key missing. Falling back to static parts catalog.")
        return get_vehicle_parts(vehicle_id)

    prompt = f"""
    Como um engenheiro mecânico automotivo sênior especialista em manutenção preventiva, gere um catálogo focado EXCLUSIVAMENTE em PEÇAS DE MANUTENÇÃO para o veículo abaixo. O objetivo é ajudar o usuário a entender a função de cada peça e a importância de trocá-la preventivamente para evitar danos maiores.

    DADOS ESPECÍFICOS DO VEÍCULO:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Motorização: {vehicle.engine_type}
    - Transmissão: {vehicle.transmission}
    - Combustível: {vehicle.fuel_type}
    - Perfil de Uso: {vehicle.usage_type}

    INSTRUÇÕES CRÍTICAS:
    1. SEJA ESPECÍFICO PARA ESTE VEÍCULO EXATO:
       - Verifique se o motor usa CORRENTE DE DISTRIBUIÇÃO ou CORREIA DENTADA (ex: 1.8 E.torQ usa corrente, não correia)
       - Ajuste todos os itens para o motor, ano e modelo exatos
       - Não inclua peças que não existem ou não são necessárias para este veículo
    
    2. SE O MOTOR USA CORRENTE DE DISTRIBUIÇÃO:
       - Substitua "Correia Dentada" por "Corrente de Distribuição"
       - Inclua "Guias da Corrente de Distribuição"
       - Inclua "Tensor da Corrente de Distribuição"
       - Marque esses itens como "Inspecção" em vez de troca periódica obrigatória

    3. SE O MOTOR USA CORREIA DENTADA:
       - Mantenha "Correia Dentada", "Tensor da Correia Dentada"
       - Inclua troca preventiva no intervalo correto para este veículo

    CATEGORIAS E ITENS (AJUSTAR CONFORME VEÍCULO):
    1. 'Filtros': 
       - Filtro de Óleo
       - Filtro de Ar do Motor
       - Filtro de Cabine (Ar-condicionado)
       - Filtro de Combustível
    
    2. 'Lubrificantes e Fluidos':
       - Óleo do Motor
       - Fluido de Freio
       - Líquido de Arrefecimento
       - Óleo de Câmbio (Automático/Manual)
       - Fluido de Direção Hidráulica (se aplicável)
    
    3. 'Sistema de Freios':
       - Pastilhas de Freio Dianteiras
       - Pastilhas de Freio Traseiras / Sapatas de Freio
       - Discos de Freio
       - Flexíveis de Freio
       - Fluido de Freio
    
    4. 'Suspensão e Direção':
       - Amortecedores Dianteiros
       - Amortecedores Traseiros
       - Coxins de Amortecedor
       - Buchas de Suspensão
       - Pivôs de Suspensão
       - Bieletas de Estabilizadora
       - Terminais de Direção
       - Caixa de Direção (inspeção)
    
    5. 'Ignição e Sistema de Distribuição':
       - Velas de Ignição
       - Bobinas de Ignição
       - Correia de Acessórios (Poly-V)
       - [CORREIA DENTADA OU CORRENTE, DEPENDENDO DO MOTOR]
       - [TENSOR OU GUIAS, DEPENDENDO DO MOTOR]
    
    6. 'Sistema de Arrefecimento':
       - Bomba d'Água
       - Válvula Termostática
       - Mangueiras do Sistema de Arrefecimento
       - Radiador (inspeção/limpeza)
       - Ventoinha do Radiador
       - Tampa do Reservatório
    
    7. 'Sistema Elétrico':
       - Bateria
       - Alternador (inspeção)
       - Motor de Partida (inspeção)
       - Fusíveis
       - Iluminação Externa e Interna
    
    8. 'Transmissão Específica':
       - SE CÂMBIO AUTOMÁTICO/CVT: Conversor de Torque, Corpo de Válvulas, Filtro do Câmbio Automático, Fluído de Transmissão ATF
       - SE CÂMBIO MANUAL: Kit de Embreagem (Platô, Disco, Rolamento), Atuador Hidráulico de Embreagem, Cabo de Seleção de Marchas
    
    9. 'Outros Itens':
       - Pneus (rodízio/balanceamento/alinhamento)
       - Bicos Injetores (limpeza)
       - Corpo de Borboleta (limpeza)

    Para cada peça, a descrição deve enfatizar:
    - O QUE ELA FAZ (Função técnica clara específica para este veículo)
    - POR QUE PREVENIR (O que acontece se não trocar? Qual o prejuízo financeiro ou risco à segurança?)

    Retorne APENAS um JSON no formato:
    {{
        "parts": [
            {{
                "id": increment_id,
                "name": "Nome da Peça de Manutenção",
                "category": "Uma das categorias acima",
                "subcategory": "Tipo de manutenção (Preventiva/Inspecção)",
                "description": "Explicação clara da função e o risco de não realizar a manutenção para este veículo",
                "image_url": "",
                "details": {{
                    "purpose": "Finalidade técnica no contexto deste veículo",
                    "location": "Onde se encontra no carro",
                    "common_problems": "Sinais de que a peça está falhando",
                    "maintenance_interval": "Intervalo recomendado (ex: 10.000km ou 1 ano, específico para este veículo)"
                }}
            }}
        ]
    }}
    Gere uma lista rica e educativa com pelo menos 20-30 itens essenciais específicos para este veículo exato.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um engenheiro mecânico sênior especialista em catálogo de peças automotivas."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        # Validar e corrigir imagens da IA
        ai_data = validate_and_fix_images(ai_data, 'parts')
        
        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year}) - {vehicle.transmission} - {vehicle.engine_type}",
            'parts': ai_data['parts']
        }), 200
    except Exception as e:
        print(f"AI Parts Error: {str(e)}. Falling back to static data.")
        return get_vehicle_parts(vehicle_id)

@app.route('/vehicle/checklist/ai/<int:vehicle_id>', methods=['GET'])
def get_vehicle_checklist_ai(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
        
    current_km = vehicle.mileage
    
    # Check if API Key is configured
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("OpenAI API Key missing. Falling back to static checklist.")
        return get_vehicle_checklist(vehicle_id)

    prompt = f"""
    Como um mecânico especialista em manutenção preventiva, gere um checklist de manutenção para um {vehicle.brand} {vehicle.model} ano {vehicle.year} com {current_km}km rodados, câmbio {vehicle.transmission}, motor {vehicle.engine_type} e perfil de uso {vehicle.usage_type}.
    
    Perfil de Uso: {vehicle.usage_type} (IMPORTANTE: Se o uso for 'Urbano/Severo', antecipe as trocas de óleo e filtros em 50%.)
    
    Considere o histórico informado pelo usuário: 
    - Última troca de óleo: {vehicle.last_oil_change}km (há {current_km - vehicle.last_oil_change}km)
    - Última troca de correia/tensão de corrente: {vehicle.last_belt_change}km (há {current_km - vehicle.last_belt_change}km)
    - Última troca de freios: {vehicle.last_brake_change}km (há {current_km - vehicle.last_brake_change}km)

    INSTRUÇÕES CRÍTICAS:
    1. SEJA ESPECÍFICO PARA ESTE VEÍCULO EXATO:
       - Verifique se o motor {vehicle.engine_type} usa CORRENTE DE DISTRIBUIÇÃO ou CORREIA DENTADA (ex: 1.8 E.torQ usa corrente, não correia)
       - Ajuste todos os itens para o motor, ano e modelo exatos
       - Não inclua peças que não existem ou não são necessárias para este veículo
    
    2. SE O MOTOR USA CORRENTE DE DISTRIBUIÇÃO:
       - Substitua "Correia Dentada" por "Corrente de Distribuição"
       - Inclua "Guias da Corrente de Distribuição"
       - Inclua "Tensor da Corrente de Distribuição"
       - Marque esses itens como inspeção, não como troca preventiva obrigatória
    
    3. SE O MOTOR USA CORREIA DENTADA:
       - Mantenha "Correia Dentada", "Tensor da Correia Dentada"
       - Inclua troca preventiva no intervalo correto para este veículo

    Gere um checklist personalizado com o que deve ser feito AGORA ou EM BREVE para este carro específico, considerando as particularidades do motor {vehicle.engine_type}.

    CATEGORIAS E ITENS PARA INCLUIR (ALINHADOS COM CATÁLOGO DE PEÇAS):
    1. Filtros: Filtro de Óleo, Filtro de Ar do Motor, Filtro de Cabine, Filtro de Combustível
    2. Lubrificantes e Fluidos: Óleo do Motor, Fluido de Freio, Líquido de Arrefecimento, Óleo de Câmbio
    3. Sistema de Freios: Pastilhas de Freio Dianteiras, Pastilhas/Sapatas Traseiras, Discos de Freio, Flexíveis de Freio
    4. Suspensão e Direção: Amortecedores, Coxins, Buchas, Pivôs, Terminais de Direção
    5. Ignição e Sistema de Distribuição: Velas de Ignição, Bobinas, Correia de Acessórios (Poly-V), [CORREIA DENTADA OU CORRENTE, DEPENDENDO DO MOTOR]
    6. Sistema de Arrefecimento: Bomba d'Água, Válvula Termostática, Mangueiras, Radiador
    7. Sistema Elétrico: Bateria, Alternador, Motor de Partida
    8. Transmissão Específica: Itens específicos para câmbio {vehicle.transmission}

    Retorne APENAS um JSON no seguinte formato:
    {{
        "checklist": [
            {{
                "id": 1,
                "name": "Nome da Peça/Serviço",
                "description": "Explicação do que deve ser verificado/trocado",
                "reason": "Por que isso é crítico para este modelo/km?",
                "priority": "URGENTE" | "PRÓXIMOS 30 DIAS" | "PRÓXIMOS 60 DIAS" | "PRÓXIMOS 90 DIAS",
                "image_url": ""
            }}
        ]
    }}
    Lógica de prioridade:
    - Se ultrapassou o prazo (ex: óleo > 10k km, correia > 50k km): use "URGENTE"
    - Se está perto do prazo: use "PRÓXIMOS 30 DIAS"
    - Se for inspeção de rotina: use "PRÓXIMOS 60 DIAS" ou "90 DIAS"
    Gere pelo menos 12-15 itens relevantes, incluindo TODAS as peças essenciais da lista acima, específicos do modelo {vehicle.model} e do câmbio {vehicle.transmission}.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um mecânico master de concessionária especialista em manutenção preventiva."},
                      {"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        # Validar e corrigir imagens da IA
        ai_data = validate_and_fix_images(ai_data, 'checklist')

        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model}",
            'mileage': current_km,
            'checklist': ai_data['checklist']
        }), 200
    except Exception as e:
        print(f"AI Checklist Error: {str(e)}. Falling back to static data.")
        return get_vehicle_checklist(vehicle_id)


@app.route('/vehicle/maintenance-tips/<int:vehicle_id>', methods=['GET'])
def get_maintenance_tips(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404

    # Check if API Key is configured
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("OpenAI API Key missing. Falling back to static maintenance tips.")
        return get_static_maintenance_tips(vehicle)

    prompt = f"""
    Como um engenheiro mecânico automotivo sênior, gere uma lista de DICAS DE MANUTENÇÃO PREVENTIVA ESPECÍFICAS para o veículo abaixo.

    DADOS DO VEÍCULO:
    - Marca: {vehicle.brand}
    - Modelo: {vehicle.model}
    - Ano: {vehicle.year}
    - Transmissão: {vehicle.transmission}
    - Motorização: {vehicle.engine_type}
    - Combustível: {vehicle.fuel_type}

    INSTRUÇÕES:
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
            response_format={ "type": "json_object" }
        )
        ai_data = json.loads(response.choices[0].message.content)

        return jsonify({
            'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year})",
            'tips': ai_data['tips']
        }), 200
    except Exception as e:
        print(f"AI Maintenance Tips Error: {str(e)}. Falling back to static data.")
        return get_static_maintenance_tips(vehicle)


def get_static_maintenance_tips(vehicle):
    """Static fallback maintenance tips."""
    tips = [
        {
            "id": 1,
            "title": "Óleo do motor",
            "content": "Verifique o nível do óleo a cada 15 dias ou antes de viagens longas. Observe nível, viscosidade e cor. Troque entre 5.000 e 10.000 km, conforme o tipo do óleo e o manual do carro."
        },
        {
            "id": 2,
            "title": "Fluidos essenciais",
            "content": "Cheque fluido de freio, direção hidráulica, embreagem (se houver), arrefecimento e limpador de para-brisa. Todos devem estar no nível correto."
        },
        {
            "id": 3,
            "title": "Calibragem dos pneus",
            "content": "Faça semanalmente com pneus frios. Pressões ideais estão no manual ou na porta do motorista."
        },
        {
            "id": 4,
            "title": "Pastilhas e discos de freio",
            "content": "Ruídos ao frear, vibração no pedal ou aumento da distância de frenagem indicam desgaste."
        },
        {
            "id": 5,
            "title": f"Câmbio {vehicle.transmission or ''}",
            "content": "Verifique vazamentos e dificuldade de engate — pode indicar desgaste no kit embreagem (para câmbio manual)."
        },
        {
            "id": 6,
            "title": "Lavagem e enceramento",
            "content": "Reduzem corrosão e protegem a pintura."
        }
    ]

    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year})",
        'tips': tips
    }), 200

@app.route('/register', methods=['POST'])
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

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Credenciais ausentes'}), 400
    
    user = User.query.filter_by(email=data['email'], password=data['password']).first()
    
    if user:
        return jsonify({'message': 'Login realizado com sucesso', 'user': user.to_dict()}), 200
    else:
        return jsonify({'error': 'Email ou senha inválidos'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logout realizado com sucesso'}), 200

@app.route('/vehicle/maintenance/<int:maintenance_id>', methods=['DELETE'])
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
    
@app.route('/vehicle/maintenance/<int:maintenance_id>', methods=['PUT', 'PATCH'])
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

@app.route('/vehicle/parts/<int:vehicle_id>', methods=['GET'])
def get_vehicle_parts(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Veículo não encontrado'}), 404
        
    transmission_type = vehicle.transmission.lower() if vehicle.transmission else 'manual'
    is_automatic = 'autom' in transmission_type
    
    # --- Fallback: Catálogo Estático de Segurança (Caso a IA falhe ou não tenha chave) ---
    parts_catalog = [
        # 1. Filtros
        {
            'id': 1,
            'name': 'Filtro de Óleo',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': f'Filtra as impurezas do óleo. Se não trocado, o óleo sujo causa atrito excessivo e pode fundir o motor {vehicle.engine_type}.',
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
            'description': 'Impede que poeira entre no motor. O acúmulo de sujeira aumenta o consumo e reduz a vida útil dos cilindros.',
            'details': {
                'purpose': 'Garantir que apenas ar limpo entre na câmara de combustão.',
                'location': 'Caixa plástica conectada à admissão do motor.',
                'common_problems': 'Perda de potência e aumento do consumo de combustível.',
                'maintenance_interval': '20.000km'
            },
            'image_url': ''
        },
        {
            'id': 3,
            'name': 'Filtro de Cabine (Ar-condicionado)',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Filtra o ar que entra no habitáculo, removendo poeira, poluição e alérgenos.',
            'details': {
                'purpose': 'Garantir ar limpo para os ocupantes e proteger o sistema de ar-condicionado.',
                'location': 'Geralmente atrás do painel, na entrada do ar externo.',
                'common_problems': 'Ar-condicionado com mau cheiro ou redução do fluxo de ar.',
                'maintenance_interval': '15.000km ou 12 meses'
            },
            'image_url': ''
        },
        {
            'id': 4,
            'name': 'Filtro de Combustível',
            'category': 'Filtros',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Filtra impurezas do combustível antes de chegar aos bicos injetores.',
            'details': {
                'purpose': 'Proteger os bicos injetores e a bomba de combustível.',
                'location': 'Na linha de combustível, próximo ao tanque ou ao motor.',
                'common_problems': 'Perda de potência, falhas na injeção ou dificuldade na partida.',
                'maintenance_interval': '30.000km'
            },
            'image_url': ''
        },

        # 2. Lubrificantes e Fluidos
        {
            'id': 10,
            'name': 'Óleo do Motor',
            'category': 'Lubrificantes e Fluidos',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Lubrifica, resfria e limpa as partes internas do motor.',
            'details': {
                'purpose': 'Reduzir atrito, dissipar calor e remover resíduos de combustão.',
                'location': 'Cárter do motor.',
                'common_problems': 'Degradação por calor, perda de viscosidade.',
                'maintenance_interval': '10.000km ou 1 ano'
            },
            'image_url': ''
        },
        {
            'id': 11,
            'name': 'Fluido de Freio',
            'category': 'Lubrificantes e Fluidos',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Transmite a força do pedal para as pinças de freio.',
            'details': {
                'purpose': 'Garantir frenagem segura e consistente.',
                'location': 'Reservatório próximo ao painel de freio e linhas hidráulicas.',
                'common_problems': 'Absorção de umidade, redução do ponto de ebulição.',
                'maintenance_interval': '2 anos'
            },
            'image_url': ''
        },
        {
            'id': 12,
            'name': 'Líquido de Arrefecimento',
            'category': 'Lubrificantes e Fluidos',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Mantém a temperatura do motor dentro dos limites ideais.',
            'details': {
                'purpose': 'Evitar superaquecimento e congelamento do sistema.',
                'location': 'Reservatório e mangueiras do sistema de arrefecimento.',
                'common_problems': 'Degradação dos aditivos anticorrosivos.',
                'maintenance_interval': 'Verificação periódica, substituição conforme manual'
            },
            'image_url': ''
        },

        # 3. Sistema de Freios
        {
            'id': 20,
            'name': 'Pastilhas de Freio Dianteiras',
            'category': 'Sistema de Freios',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Componente de atrito que para o carro. Ignorar o desgaste pode destruir os discos de freio.',
            'details': {
                'purpose': 'Transformar energia cinética em calor para frear o veículo.',
                'location': 'Dentro das pinças de freio nas rodas dianteiras.',
                'common_problems': 'Assobio agudo ao frear ou perda de eficiência na frenagem.',
                'maintenance_interval': 'Verificar a cada 10.000km'
            },
            'image_url': ''
        },
        {
            'id': 21,
            'name': 'Pastilhas/Sapatas de Freio Traseiras',
            'category': 'Sistema de Freios',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Complementa a frenagem dianteira, garantindo equilíbrio.',
            'details': {
                'purpose': 'Auxiliar na frenagem e manter a estabilidade.',
                'location': 'Rodas traseiras, pinças ou tambores.',
                'common_problems': 'Desgaste irregular ou ruído.',
                'maintenance_interval': 'Verificar a cada 10.000km'
            },
            'image_url': ''
        },
        {
            'id': 22,
            'name': 'Discos de Freio',
            'category': 'Sistema de Freios',
            'subcategory': 'Manutenção Corretiva',
            'description': 'Superfície onde as pastilhas aplicam pressão para frear.',
            'details': {
                'purpose': 'Proporcionar superfície de atrito uniforme.',
                'location': 'Anexados às cubas das rodas.',
                'common_problems': 'Deformação, rachaduras ou desgaste excessivo.',
                'maintenance_interval': 'Verificar a cada 20.000km'
            },
            'image_url': ''
        },

        # 4. Suspensão e Direção
        {
            'id': 30,
            'name': 'Amortecedores Dianteiros',
            'category': 'Suspensão e Direção',
            'subcategory': 'Manutenção Preventiva',
            'description': f'Amortecedores pressurizados para {vehicle.brand} que controlam as oscilações.',
            'details': {
                'purpose': 'Controlar as oscilações da mola e manter o pneu no chão.',
                'location': 'Torres de suspensão dianteiras.',
                'common_problems': 'Vazamento de óleo ou perda de ação.',
                'maintenance_interval': '60.000km a 80.000km'
            },
            'image_url': ''
        },
        {
            'id': 31,
            'name': 'Amortecedores Traseiros',
            'category': 'Suspensão e Direção',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Mantêm a estabilidade traseira e tração em frenagens.',
            'details': {
                'purpose': 'Controlar oscilações e manter contato do pneu com o solo.',
                'location': 'Eixo traseiro.',
                'common_problems': 'Vazamento ou perda de eficácia.',
                'maintenance_interval': '60.000km a 80.000km'
            },
            'image_url': ''
        },
        {
            'id': 32,
            'name': 'Buchas de Suspensão',
            'category': 'Suspensão e Direção',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Isolam vibrações e permitem movimento controlado das peças.',
            'details': {
                'purpose': 'Absorver impactos e manter geometria da suspensão.',
                'location': 'Pontos de articulação da suspensão.',
                'common_problems': 'Rachaduras, deformação ou ruídos.',
                'maintenance_interval': 'Inspecionar a cada 40.000km'
            },
            'image_url': ''
        },
        {
            'id': 33,
            'name': 'Terminais de Direção',
            'category': 'Suspensão e Direção',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Conectam a caixa de direção às rodas.',
            'details': {
                'purpose': 'Transmitir o movimento da direção às rodas.',
                'location': 'Extremidades das barras de direção.',
                'common_problems': 'Folga, instabilidade ou desgaste irregular dos pneus.',
                'maintenance_interval': 'Inspecionar a cada 20.000km'
            },
            'image_url': ''
        },

        # 5. Ignição e Correias
        {
            'id': 40,
            'name': 'Velas de Ignição',
            'category': 'Ignição e Correias',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Responsáveis pela faísca que queima o combustível na câmara de combustão.',
            'details': {
                'purpose': 'Iniciar a combustão de forma eficiente e sincronizada.',
                'location': 'No cabeçote, conectadas às bobinas.',
                'common_problems': 'Dificuldade na partida e motor "falhando" em marcha lenta.',
                'maintenance_interval': '40.000km a 60.000km'
            },
            'image_url': ''
        },
        {
            'id': 41,
            'name': 'Bobinas de Ignição',
            'category': 'Ignição e Correias',
            'subcategory': 'Inspecão',
            'description': 'Geram a alta tensão necessária para as velas produzirem a faísca.',
            'details': {
                'purpose': 'Amplificar a tensão da bateria para alimentar as velas.',
                'location': 'Sobre as velas ou próximas ao cabeçote.',
                'common_problems': 'Falha na ignição, perda de potência.',
                'maintenance_interval': 'Inspecionar a cada 40.000km'
            },
            'image_url': ''
        },
        {
            'id': 42,
            'name': 'Correia de Acessórios (Poly-V)',
            'category': 'Ignição e Correias',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Aciona alternador, bomba d\'água, compressor de ar-condicionado e outros acessórios.',
            'details': {
                'purpose': 'Transmitir rotação do motor para os acessórios.',
                'location': 'Frente do motor.',
                'common_problems': 'Rachaduras, desgaste ou ruptura.',
                'maintenance_interval': '60.000km ou 4 anos'
            },
            'image_url': ''
        },
        {
            'id': 43,
            'name': 'Correia Dentada / Corrente de Distribuição',
            'category': 'Ignição e Correias',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Sincroniza o movimento do virabrequim com o cabeçote do motor.',
            'details': {
                'purpose': 'Garantir sincronismo preciso entre válvulas e pistões.',
                'location': 'Internamente ao motor, protegido por capa.',
                'common_problems': 'Desgaste, rompimento (causa danos graves ao motor).',
                'maintenance_interval': '50.000km a 100.000km (ver manual)'
            },
            'image_url': ''
        },

        # 6. Sistema de Arrefecimento
        {
            'id': 50,
            'name': 'Bomba d\'Água',
            'category': 'Sistema de Arrefecimento',
            'subcategory': 'Manutenção Preventiva',
            'description': f'Faz o fluído de arrefecimento circular pelo motor e radiador do {vehicle.model}.',
            'details': {
                'purpose': 'Circular o líquido de arrefecimento para manter temperatura ideal.',
                'location': 'Acoplado ao bloco do motor, movido pela correia.',
                'common_problems': 'Vazamentos no selo mecânico ou ruído no rolamento.',
                'maintenance_interval': 'Trocar com a correia dentada'
            },
            'image_url': ''
        },
        {
            'id': 51,
            'name': 'Válvula Termostática',
            'category': 'Sistema de Arrefecimento',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Controla a temperatura do motor, abrindo quando atinge o ponto ideal.',
            'details': {
                'purpose': 'Permitir que o motor atinja temperatura de trabalho rapidamente.',
                'location': 'Na saída do bloco do motor, em direção ao radiador.',
                'common_problems': 'Travar aberta (motor não esquenta) ou fechada (superaquecimento).',
                'maintenance_interval': 'Trocar a cada 4 anos'
            },
            'image_url': ''
        },
        {
            'id': 52,
            'name': 'Radiador',
            'category': 'Sistema de Arrefecimento',
            'subcategory': 'Inspecão',
            'description': 'Dissipa o calor do fluído de arrefecimento para o ambiente.',
            'details': {
                'purpose': 'Resfriar o fluído de arrefecimento que vem do motor.',
                'location': 'Frente do veículo, atrás da grade.',
                'common_problems': 'Entupimento, vazamentos ou aletas danificadas.',
                'maintenance_interval': 'Limpar/inspecionar a cada 2 anos'
            },
            'image_url': ''
        },

        # 7. Sistema Elétrico
        {
            'id': 60,
            'name': 'Bateria',
            'category': 'Sistema Elétrico',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Armazena energia elétrica para partida e sistemas com o motor desligado.',
            'details': {
                'purpose': 'Fornecer corrente para partida e sistemas elétricos.',
                'location': 'Geralmente no compartimento do motor.',
                'common_problems': 'Perda de capacidade, sulfatação ou terminais corroídos.',
                'maintenance_interval': 'Verificar a cada 6 meses, vida útil de 3-5 anos'
            },
            'image_url': ''
        },
        {
            'id': 61,
            'name': 'Alternador',
            'category': 'Sistema Elétrico',
            'subcategory': 'Geração de Energia',
            'description': 'Gera energia elétrica para o veículo e carrega a bateria com o motor ligado.',
            'details': {
                'purpose': 'Transformar energia mecânica em elétrica.',
                'location': 'Frente do motor, movido pela correia de acessórios.',
                'common_problems': 'Desgaste das escovas ou falha no regulador de voltagem.',
                'maintenance_interval': 'Inspecionar a cada 40.000km'
            },
            'image_url': ''
        },

        # 9. Outros Itens
        {
            'id': 70,
            'name': 'Pneus (Rodízio/Balanceamento)',
            'category': 'Outros Itens',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Garante desgaste uniforme e longa vida útil dos pneus.',
            'details': {
                'purpose': 'Distribuir o desgaste igualmente entre todos os pneus.',
                'location': 'Todas as rodas do veículo.',
                'common_problems': 'Desgaste irregular, vibrações.',
                'maintenance_interval': 'Rodízio a cada 10.000km'
            },
            'image_url': ''
        },
        {
            'id': 71,
            'name': 'Alinhamento de Direção',
            'category': 'Outros Itens',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Garante que as rodas estejam paralelas e com ângulos corretos.',
            'details': {
                'purpose': 'Evitar desgaste irregular dos pneus e manter estabilidade.',
                'location': 'Todos os ângulos da suspensão e direção.',
                'common_problems': 'Puxar para um lado, volante descentralizado.',
                'maintenance_interval': 'A cada revisão ou após impactos'
            },
            'image_url': ''
        },
        {
            'id': 72,
            'name': 'Corpo de Borboleta (Limpeza)',
            'category': 'Outros Itens',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Controla a quantidade de ar que entra no motor.',
            'details': {
                'purpose': 'Garantir fluxo de ar preciso para a combustão.',
                'location': 'Na admissão, após o filtro de ar.',
                'common_problems': 'Acúmulo de sujeira, instabilidade em marcha lenta.',
                'maintenance_interval': 'Limpar a cada 30.000km'
            },
            'image_url': ''
        },
        {
            'id': 73,
            'name': 'Bicos Injetores (Limpeza)',
            'category': 'Outros Itens',
            'subcategory': 'Manutenção Preventiva',
            'description': 'Pulverizam o combustível na câmara de combustão ou na admissão.',
            'details': {
                'purpose': 'Garantir atomização ideal do combustível.',
                'location': 'No coletor de admissão ou cabeçote.',
                'common_problems': 'Entupimento, pulverização irregular, aumento do consumo.',
                'maintenance_interval': 'Limpar a cada 40.000km'
            },
            'image_url': ''
        }
    ]

    # --- Peças de Transmissão Específicas (Depende do Câmbio) ---
    if is_automatic:
        parts_catalog.extend([
            {
                'id': 100,
                'name': 'Conversor de Torque',
                'category': 'Transmissão Específica',
                'subcategory': f'Automático ({vehicle.transmission})',
                'description': f'Acoplamento fluido para o câmbio automático do {vehicle.model}.',
                'details': {
                    'purpose': 'Transmitir o torque do motor para a caixa sem embreagem mecânica.',
                    'location': 'Entre o motor e a transmissão.',
                    'common_problems': 'Patinamento ou vibração excessiva.',
                    'maintenance_interval': 'Troca de fluido a cada 60.000km'
                },
                'image_url': ''
            },
            {
                'id': 101,
                'name': 'Corpo de Válvulas',
                'category': 'Transmissão Específica',
                'subcategory': f'Automático ({vehicle.transmission})',
                'description': 'Cérebro hidráulico da transmissão automática.',
                'details': {
                    'purpose': 'Controlar o fluxo de fluido para as trocas de marcha.',
                    'location': 'Interior da caixa de câmbio.',
                    'common_problems': 'Trancos ou atrasos nas trocas.',
                    'maintenance_interval': 'Inspecionar a cada 40.000km'
                },
                'image_url': ''
            },
            {
                'id': 102,
                'name': 'Filtro do Câmbio Automático',
                'category': 'Transmissão Específica',
                'subcategory': f'Automático ({vehicle.transmission})',
                'description': 'Filtro interno responsável pela limpeza do fluído ATF.',
                'details': {
                    'purpose': 'Reter limalhas e impurezas do sistema hidráulico do câmbio.',
                    'location': 'Dentro do cárter da transmissão.',
                    'common_problems': 'Entupimento causando perda de pressão e queima dos discos.',
                    'maintenance_interval': 'Trocar a cada 60.000km'
                },
                'image_url': ''
            },
            {
                'id': 103,
                'name': 'Fluído de Transmissão ATF',
                'category': 'Transmissão Específica',
                'subcategory': f'Automático ({vehicle.transmission})',
                'description': 'Óleo específico para transmissões automáticas.',
                'details': {
                    'purpose': 'Lubrificação, arrefecimento e transferência de força hidráulica.',
                    'location': 'Sistema de transmissão.',
                    'common_problems': 'Degradação por calor, causando patinação.',
                    'maintenance_interval': 'Trocar a cada 60.000km'
                },
                'image_url': ''
            }
        ])
    else:
        parts_catalog.extend([
            {
                'id': 110,
                'name': 'Kit de Embreagem',
                'category': 'Transmissão Específica',
                'subcategory': 'Manual',
                'description': f'Kit completo (platô, disco e rolamento) para {vehicle.brand}.',
                'details': {
                    'purpose': 'Acoplamento e desacoplamento do motor com o câmbio.',
                    'location': 'Entre o motor e a caixa de câmbio.',
                    'common_problems': 'Embreagem "patinando" ou pedal pesado.',
                    'maintenance_interval': '80.000km a 100.000km'
                },
                'image_url': ''
            },
            {
                'id': 111,
                'name': 'Atuador Hidráulico de Embreagem',
                'category': 'Transmissão Específica',
                'subcategory': 'Manual',
                'description': 'Componente que aciona a embreagem via pressão hidráulica.',
                'details': {
                    'purpose': 'Empurrar o platô para liberar o disco de embreagem.',
                    'location': 'Acoplado ao câmbio ou dentro da caixa seca.',
                    'common_problems': 'Vazamento de fluído de freio e pedal bobo.',
                    'maintenance_interval': 'Trocar com o kit de embreagem'
                },
                'image_url': ''
            },
            {
                'id': 112,
                'name': 'Cabo de Seleção de Marchas',
                'category': 'Transmissão Específica',
                'subcategory': 'Manual',
                'description': 'Cabo que transmite o movimento da alavanca para o câmbio.',
                'details': {
                    'purpose': 'Selecionar e engatar as marchas mecanicamente.',
                    'location': 'Entre a alavanca de câmbio e a caixa.',
                    'common_problems': 'Rompimento ou folga excessiva nas buchas.',
                    'maintenance_interval': 'Inspecionar a cada 40.000km'
                },
                'image_url': ''
            }
        ])

    return jsonify({
        'vehicle': f"{vehicle.brand} {vehicle.model} ({vehicle.year}) - {vehicle.transmission} - {vehicle.engine_type}",
        'parts': parts_catalog
    }), 200

if __name__ == '__main__':
    create_tables()
    app.run(host='0.0.0.0', port=5000, debug=True)
