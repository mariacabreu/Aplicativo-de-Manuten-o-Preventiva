import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  Image,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Platform,
  StyleSheet
} from 'react-native';
import { Ionicons, FontAwesome5 } from '@expo/vector-icons';
import axios from 'axios';
import { useFocusEffect } from '@react-navigation/native';
import API_BASE_URL from '../../api';
import CustomDropdown from '../Vehicle/CustomDropDown';
import AMPAlertModal from '../Common/AMPAlertModal';

const VehicleEditScreen = ({ navigation, route }) => {
  const user = route.params?.user;

  const [vehicle, setVehicle] = useState(null);
  const [loadingVehicles, setLoadingVehicles] = useState(true);

  // ----- Estado do formulário de edição -----
  const [brands, setBrands] = useState([]);
  const [models, setModels] = useState([]);
  const [engines, setEngines] = useState([]);
  const [years, setYears] = useState([]);

  const [selectedBrand, setSelectedBrand] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [transmission, setTransmission] = useState('');
  const [engineType, setEngineType] = useState('');
  const [usageType, setUsageType] = useState('Misto');
  const [mileage, setMileage] = useState('');
  const [fuelType, setFuelType] = useState('Gasolina');
  const [openDropdown, setOpenDropdown] = useState(null);
  const [savingVehicle, setSavingVehicle] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [alertModalVisible, setAlertModalVisible] = useState(false);
  const [alertModalData, setAlertModalData] = useState({
    type: 'info',
    title: '',
    message: '',
    confirmButtonText: 'Ok',
    onConfirm: () => setAlertModalVisible(false),
  });

  const transmissionOptions = [
    { label: 'Selecione o Câmbio', value: '' },
    { label: 'Manual', value: 'Manual' },
    { label: 'Automático', value: 'Automático' },
    { label: 'Automatizado', value: 'Automatizado' },
    { label: 'CVT', value: 'CVT' }
  ];

  const usageTypeOptions = [
    { label: 'Urbano (Cidade/Trânsito)', value: 'Urbano' },
    { label: 'Rodoviário (Estrada)', value: 'Rodoviário' },
    { label: 'Misto (Cidade e Estrada)', value: 'Misto' },
    { label: 'Trabalho/Severo (Uber/Entrega)', value: 'Severo' }
  ];

  const fuelTypeOptions = [
    { label: 'Gasolina', value: 'Gasolina' },
    { label: 'Etanol', value: 'Etanol' },
    { label: 'Flex', value: 'Flex' },
    { label: 'Diesel', value: 'Diesel' },
    { label: 'Híbrido', value: 'Híbrido' },
    { label: 'Elétrico', value: 'Elétrico' }
  ];

  useEffect(() => {
    fetchVehicles();
    fetchBrands();
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (!user?.id) {
        return undefined;
      }

      fetchVehicles();
      return undefined;
    }, [user?.id])
  );

  const fetchVehicles = async () => {
    if (!user?.id) {
      setLoadingVehicles(false);
      return;
    }
    try {
      setLoadingVehicles(true);
      const response = await axios.get(`${API_BASE_URL}/user/vehicles/${user.id}`);
      const vehicles = response.data.vehicles || [];
      if (vehicles.length > 0) {
        setVehicle(vehicles[0]);
      }
    } catch (error) {
      console.error('Erro ao buscar veículos:', error);
    } finally {
      setLoadingVehicles(false);
    }
  };

  const fetchBrands = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/vehicle/brands`);
      const formattedBrands = [{ label: 'Selecione a Marca', value: '' }, ...response.data.map(b => ({ label: b, value: b }))];
      setBrands(formattedBrands);
    } catch (error) {
      console.error('Error fetching brands:', error);
    }
  };

  const fetchModels = async (brand) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/vehicle/models/${brand}`);
      setModels([{ label: 'Selecione o Modelo', value: '' }, ...response.data.map(m => ({ label: m, value: m }))]);
    } catch (error) {
      console.error('Error fetching models:', error);
    }
  };

  const fetchEngines = async (brand, model) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/vehicle/engines/${brand}/${model}`);
      setEngines([{ label: 'Selecione a Motorização', value: '' }, ...response.data.map(e => ({ label: e, value: e }))]);
    } catch (error) {
      console.error('Error fetching engines:', error);
    }
  };

  const fetchYears = async (brand, model) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/vehicle/years/${brand}/${model}`);
      setYears([{ label: 'Selecione o Ano', value: '' }, ...response.data.map(y => ({ label: y.toString(), value: y.toString() }))]);
    } catch (error) {
      console.error('Error fetching years:', error);
    }
  };

  const handleBrandChange = (brand) => {
    setSelectedBrand(brand);
    setSelectedModel('');
    setEngineType('');
    setSelectedYear('');
    if (brand) {
      fetchModels(brand);
    } else {
      setModels([]);
      setEngines([]);
      setYears([]);
    }
  };

  const handleModelChange = (model) => {
    setSelectedModel(model);
    setEngineType('');
    setSelectedYear('');
    if (model) {
      fetchEngines(selectedBrand, model);
      fetchYears(selectedBrand, model);
    } else {
      setEngines([]);
      setYears([]);
    }
  };

  const handleYearChange = (year) => {
    setSelectedYear(year);
    setEngineType('');
    if (selectedBrand && selectedModel) {
      fetchEngines(selectedBrand, selectedModel);
    }
  };

  const openEditForm = useCallback(async (vehicleData) => {
    setIsEditing(true);
    setSelectedBrand(vehicleData.brand);
    setSelectedModel(vehicleData.model);
    setSelectedYear(vehicleData.year ? vehicleData.year.toString() : '');
    setTransmission(vehicleData.transmission || '');
    setEngineType(vehicleData.engine_type || '');
    setUsageType(vehicleData.usage_type || 'Misto');
    setMileage(vehicleData.mileage ? vehicleData.mileage.toString() : '');
    setFuelType(vehicleData.fuel_type || 'Gasolina');

    if (vehicleData.brand) {
      await fetchModels(vehicleData.brand);
    }
    if (vehicleData.brand && vehicleData.model) {
      await fetchEngines(vehicleData.brand, vehicleData.model);
      await fetchYears(vehicleData.brand, vehicleData.model);
    }
  }, []);

  const closeEditForm = () => {
    setIsEditing(false);
    setOpenDropdown(null);
  };

  const handleSaveVehicle = async () => {
    if (!selectedBrand || !selectedModel || !selectedYear) {
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: 'Por favor, preencha a marca, modelo e ano do veículo.',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
      return;
    }

    if (!vehicle?.id) {
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: 'Veículo inválido para edição. Tente recarregar a tela.',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
      return;
    }

    const parsedYear = parseInt(selectedYear, 10);
    if (Number.isNaN(parsedYear)) {
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: 'Ano do veículo é inválido.',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
      return;
    }

    const parsedMileage = mileage && mileage.toString().trim() !== ''
      ? parseInt(mileage.toString().replace(/\D/g, ''), 10)
      : 0;

    try {
      setSavingVehicle(true);
      const payload = {
        brand: selectedBrand ? selectedBrand.toString().trim() : '',
        model: selectedModel ? selectedModel.toString().trim() : '',
        year: Number.isNaN(parsedYear) ? vehicle.year : parsedYear,
        transmission: transmission || '',
        engine_type: engineType || '',
        usage_type: usageType || 'Misto',
        mileage: Number.isNaN(parsedMileage) ? 0 : parsedMileage,
        fuel_type: fuelType || ''
      };

      console.log(`PUT /vehicle/${vehicle.id} payload:`, payload);

      const response = await axios.put(`${API_BASE_URL}/vehicle/${vehicle.id}`, payload, {
        timeout: 15000,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.data?.vehicle) {
        setVehicle(response.data.vehicle);
      }

      setAlertModalData({
        type: 'success',
        title: 'Sucesso',
        message: response.data?.message || 'Veículo atualizado com sucesso!',
        confirmButtonText: 'Ok',
        onConfirm: () => {
          setAlertModalVisible(false);
          closeEditForm();
          fetchVehicles();
        },
      });
      setAlertModalVisible(true);
    } catch (error) {
      console.error('Erro ao salvar veículo:', error?.response?.data || error?.message || error);
      let message = 'Erro ao salvar veículo. Tente novamente.';
      if (error?.response?.data?.error) {
        message = error.response.data.error;
      } else if (error?.message?.includes('Network') || error?.code === 'ERR_NETWORK') {
        message = 'Erro de conexão. Verifique sua internet e tente novamente.';
      } else if (error?.code === 'ECONNABORTED') {
        message = 'Tempo limite excedido. Tente novamente.';
      }
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: message,
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
    } finally {
      setSavingVehicle(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#000" />
        </TouchableOpacity>
        <View style={styles.logoContainer} pointerEvents="none">
          <Image
            source={require('../../assets/logo.png')}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <Text style={styles.headerTitle}>MEU VEÍCULO</Text>
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={true}
        keyboardShouldPersistTaps="handled"
      >
        {!isEditing && (
          <>
            {loadingVehicles ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#2C2C2C" />
                <Text style={styles.loadingText}>Carregando veículo...</Text>
              </View>
            ) : (
              <>
                {!vehicle && (
                  <View style={styles.emptyState}>
                    <FontAwesome5 name="car-side" size={40} color="#CCC" />
                    <Text style={styles.emptyStateText}>Nenhum veículo cadastrado ainda.</Text>
                  </View>
                )}

                {vehicle && (
                  <View style={styles.vehicleCard}>
                    <View style={styles.vehicleCardIcon}>
                      <FontAwesome5 name="car" size={22} color="#2C2C2C" />
                    </View>
                    <View style={styles.vehicleCardInfo}>
                      <Text style={styles.vehicleCardTitle}>
                        {vehicle.brand} {vehicle.model}
                      </Text>
                      <Text style={styles.vehicleCardSubtitle}>
                        {vehicle.year} • {vehicle.engine_type || 'Motorização não informada'}
                      </Text>
                      <Text style={styles.vehicleCardSubtitle}>
                        {vehicle.transmission || 'Câmbio N/D'} • {vehicle.mileage ? `${vehicle.mileage.toLocaleString('pt-BR')} km` : '0 km'}
                      </Text>
                    </View>
                    <TouchableOpacity
                      style={styles.vehicleCardEditButton}
                      onPress={() => openEditForm(vehicle)}
                    >
                      <Ionicons name="create-outline" size={20} color="#2C2C2C" />
                    </TouchableOpacity>
                  </View>
                )}
              </>
            )}
          </>
        )}

        {isEditing && (
          <View style={styles.formCard}>
            <View style={styles.formHeader}>
              <TouchableOpacity onPress={closeEditForm} style={styles.formBackButton}>
                <Ionicons name="arrow-back" size={20} color="#2C2C2C" />
                <Text style={styles.formBackButtonText}>Voltar</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.infoText}>
              Apenas veículos compatíveis com OBD-II Bluetooth e com documentação de API disponível são listados.
            </Text>

            <CustomDropdown
              label="Marca do Carro"
              items={brands}
              selectedValue={selectedBrand}
              onSelect={handleBrandChange}
              placeholder="Selecione a Marca"
              isOpen={openDropdown === 'brand'}
              setIsOpen={(open) => setOpenDropdown(open ? 'brand' : null)}
              onOpen={() => setOpenDropdown('brand')}
              enabled={true}
            />

            <CustomDropdown
              label="Modelo do Carro"
              items={models}
              selectedValue={selectedModel}
              onSelect={handleModelChange}
              placeholder="Selecione o Modelo"
              enabled={!!selectedBrand}
              isOpen={openDropdown === 'model'}
              setIsOpen={(open) => setOpenDropdown(open ? 'model' : null)}
              onOpen={() => setOpenDropdown('model')}
            />

            <CustomDropdown
              label="Ano do Carro"
              items={years}
              selectedValue={selectedYear}
              onSelect={handleYearChange}
              placeholder="Selecione o Ano"
              enabled={!!selectedModel}
              isOpen={openDropdown === 'year'}
              setIsOpen={(open) => setOpenDropdown(open ? 'year' : null)}
              onOpen={() => setOpenDropdown('year')}
            />

            <CustomDropdown
              label="Câmbio"
              items={transmissionOptions}
              selectedValue={transmission}
              onSelect={setTransmission}
              placeholder="Selecione o Câmbio"
              enabled={true}
              isOpen={openDropdown === 'transmission'}
              setIsOpen={(open) => setOpenDropdown(open ? 'transmission' : null)}
              onOpen={() => setOpenDropdown('transmission')}
            />

            <CustomDropdown
              label="Motorização (Contexto para IA)"
              items={engines}
              selectedValue={engineType}
              onSelect={setEngineType}
              placeholder="Selecione a Motorização"
              enabled={!!selectedBrand && !!selectedModel && !!selectedYear}
              isOpen={openDropdown === 'engine'}
              setIsOpen={(open) => setOpenDropdown(open ? 'engine' : null)}
              onOpen={() => setOpenDropdown('engine')}
            />

            <CustomDropdown
              label="Perfil de Uso (Recomendações IA)"
              items={usageTypeOptions}
              selectedValue={usageType}
              onSelect={setUsageType}
              placeholder="Selecione o Perfil de Uso"
              enabled={true}
              isOpen={openDropdown === 'usage'}
              setIsOpen={(open) => setOpenDropdown(open ? 'usage' : null)}
              onOpen={() => setOpenDropdown('usage')}
            />

            <View style={styles.inputContainer}>
              <Text style={styles.label}>Quilometragem</Text>
              <TextInput
                style={styles.input}
                placeholder="Ex: 50000"
                value={mileage}
                onChangeText={setMileage}
                keyboardType="numeric"
                editable={true}
              />
            </View>

            <CustomDropdown
              label="Combustível"
              items={fuelTypeOptions}
              selectedValue={fuelType}
              onSelect={setFuelType}
              placeholder="Selecione o Combustível"
              enabled={true}
              isOpen={openDropdown === 'fuel'}
              setIsOpen={(open) => setOpenDropdown(open ? 'fuel' : null)}
              onOpen={() => setOpenDropdown('fuel')}
            />

            <View style={styles.actionButtonsContainer}>
              <TouchableOpacity style={styles.cancelButton} onPress={closeEditForm}>
                <Text style={styles.cancelButtonText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveButton} onPress={handleSaveVehicle} disabled={savingVehicle}>
                {savingVehicle ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Text style={styles.saveButtonText}>Salvar Alterações</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>
      
      <AMPAlertModal
        visible={alertModalVisible}
        type={alertModalData.type}
        title={alertModalData.title}
        message={alertModalData.message}
        confirmButtonText={alertModalData.confirmButtonText}
        onConfirm={alertModalData.onConfirm}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#ffffff',
    ...Platform.select({
      web: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      },
      default: {
        flex: 1
      }
    })
  },
  header: {
    position: 'relative',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 40,
    paddingBottom: 20,
    backgroundColor: '#fff'
  },
  backButton: {
    width: 40,
    zIndex: 2,
    alignSelf: 'flex-start'
  },
  logoContainer: {
    position: 'absolute',
    top: 40,
    bottom: 16,
    left: 0,
    right: 0,
    justifyContent: 'center',
    alignItems: 'center'
  },
  headerLogo: {
    width: 120,
    height: 60
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#000',
    marginTop: 6,
    letterSpacing: 0.5
  },
  scrollView: {
    flex: 1,
    ...Platform.select({
      web: {
        overflowY: 'scroll'
      }
    })
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 100
  },
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 60
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#666'
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
    marginBottom: 10
  },
  emptyStateText: {
    marginTop: 12,
    fontSize: 14,
    color: '#999',
    textAlign: 'center'
  },
  vehicleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F7F7F7',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#EEEEEE'
  },
  vehicleCardIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFCF00',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14
  },
  vehicleCardInfo: {
    flex: 1
  },
  vehicleCardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#1A1A1A'
  },
  vehicleCardSubtitle: {
    fontSize: 12,
    color: '#777',
    marginTop: 2
  },
  vehicleCardEditButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E0E0E0'
  },
  formCard: {
    borderWidth: 1,
    borderColor: '#00000022',
    borderRadius: 15,
    padding: 20
  },
  formHeader: {
    marginBottom: 16
  },
  formBackButton: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  formBackButtonText: {
    marginLeft: 6,
    fontSize: 14,
    fontWeight: '600',
    color: '#2C2C2C'
  },
  infoText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 20,
    fontStyle: 'italic'
  },
  inputContainer: {
    marginBottom: 20
  },
  label: {
    fontSize: 14,
    color: '#333',
    marginBottom: 8,
    fontWeight: '600'
  },
  input: {
    borderWidth: 1,
    borderColor: '#00000033',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15
  },
  actionButtonsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10
  },
  cancelButton: {
    flex: 1,
    backgroundColor: '#F0F0F0',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginRight: 10
  },
  cancelButtonText: {
    color: '#333',
    fontSize: 14,
    fontWeight: '600'
  },
  saveButton: {
    flex: 1,
    backgroundColor: '#2C2C2C',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center'
  },
  saveButtonText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600'
  },
  bottomSpacer: {
    height: 60
  }
});

export default VehicleEditScreen;
