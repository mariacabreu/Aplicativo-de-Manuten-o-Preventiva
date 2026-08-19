import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  ActivityIndicator,
  Image
} from 'react-native';
import { MaterialCommunityIcons, Ionicons, FontAwesome5 } from '@expo/vector-icons';
import axios from 'axios';
import { useFocusEffect } from '@react-navigation/native';
import API_BASE_URL from '../../api';
import BottomNav from '../NavBar/BottomNav';

const safeParse = (value, fallback) => {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
};

const normalizeScan = (scan) => {
  if (!scan) return null;
  return {
    ...scan,
    dtc_codes: safeParse(scan.dtc_codes, []),
    live_data: safeParse(scan.live_data, {}),
  };
};

const OBDHistoryScreen = ({ navigation, route }) => {
  const loggedUser = route.params?.user;

  const [vehicle, setVehicle] = useState(null);
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [analyzingId, setAnalyzingId] = useState(null);
  const [analysisData, setAnalysisData] = useState({}); // key: scanId, value: analysis data

  useEffect(() => {
    fetchVehicleAndScans();
  }, []);

  const fetchVehicleAndScans = async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true); else setLoading(true);
      const userId = loggedUser?.id || 1;
      const statusResponse = await axios.get(`${API_BASE_URL}/user/status/${userId}`, { timeout: 20000 });

      let v = null;
      if (statusResponse.data?.vehicle) v = statusResponse.data.vehicle;
      else if (Array.isArray(statusResponse.data?.vehicles) && statusResponse.data.vehicles.length > 0) v = statusResponse.data.vehicles[0];

      if (!v) {
        setVehicle(null);
        setScans([]);
        return;
      }

      setVehicle(v);

      const scansResponse = await axios.get(
        `${API_BASE_URL}/vehicle/obd-scans/${v.id}`,
        { timeout: 20000 }
      );
      const rawScans = Array.isArray(scansResponse.data?.scans) ? scansResponse.data.scans : [];
      setScans(rawScans.map(normalizeScan).filter(Boolean));
    } catch (error) {
      console.error('Erro ao buscar histórico de scanner:', error);
      setScans([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      if (!loggedUser?.id) {
        return undefined;
      }

      fetchVehicleAndScans();
      return undefined;
    }, [loggedUser?.id])
  );

  const formatDate = (isoString) => {
    if (!isoString) return 'Data desconhecida';
    try {
      const date = new Date(isoString);
      return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return isoString;
    }
  };

  const toggleExpand = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const severityColor = (severity) => {
    if (severity === 'high') return '#FF5722';
    if (severity === 'medium') return '#FFC107';
    return '#8BC34A';
  };
  
  const handleAnalyzeScan = async (scanId) => {
    try {
      setAnalyzingId(scanId);
      const response = await axios.get(`${API_BASE_URL}/vehicle/obd-scan/analyze/${scanId}`, { timeout: 60000 });
      const data = response.data || {};
      const analysisStr = typeof data.analysis === 'string' ? data.analysis : null;
      const recs = Array.isArray(data.recommendations) ? data.recommendations : [];
      const abn = Array.isArray(data.abnormal_values) ? data.abnormal_values : [];
      setAnalysisData(prev => ({
        ...prev,
        [scanId]: {
          analysis: analysisStr,
          recommendations: recs,
          abnormal_values: abn,
        }
      }));
    } catch (err) {
      console.error('Erro ao analisar scan:', err?.message || err);
    } finally {
      setAnalyzingId(null);
    }
  };

  const renderConditionGrid = (liveData) => {
    if (!liveData || Object.keys(liveData).length === 0) {
      return <Text style={styles.noConditionText}>Nenhuma condição registrada neste scan.</Text>;
    }

    const items = [
      { key: 'rpm', label: 'RPM', unit: '', icon: 'tachometer' },
      { key: 'speed', label: 'Velocidade', unit: ' km/h', icon: 'speedometer' },
      { key: 'coolantTemp', label: 'Temp. Motor', unit: '°C', icon: 'thermometer' },
      { key: 'fuelLevel', label: 'Combustível', unit: '%', icon: 'gas-station' },
      { key: 'engineLoad', label: 'Carga do Motor', unit: '%', icon: 'car-battery' },
      { key: 'throttlePosition', label: 'Acelerador', unit: '%', icon: 'engine' },
      { key: 'intakeManifoldPressure', label: 'Pressão Coletor', unit: ' kPa', icon: 'gauge' },
      { key: 'ambientTemp', label: 'Temp. Ambiente', unit: '°C', icon: 'weather-sunny' },
      { key: 'airIntakeTemp', label: 'Temp. Ar Adm.', unit: '°C', icon: 'oil' },
      { key: 'maf', label: 'Fluxo Ar (MAF)', unit: ' g/s', icon: 'weather-windy' },
      { key: 'batteryVoltage', label: 'Tensão Bateria', unit: ' V', icon: 'car-battery' },
      { key: 'fuelPressure', label: 'Pressão Comb.', unit: ' kPa', icon: 'fire' },
      { key: 'oilTemp', label: 'Temp. Óleo', unit: '°C', icon: 'thermometer-lines' },
      { key: 'lambda', label: 'Sonda Lambda', unit: ' λ', icon: 'omega' },
      { key: 'timingAdvance', label: 'Avanço Ignição', unit: '°', icon: 'clock-fast' },
      { key: 'egr', label: 'EGR', unit: '%', icon: 'valve' },
      { key: 'evapSystemVaporPressure', label: 'Pressão Evap.', unit: ' Pa', icon: 'waves' },
      { key: 'catalystTemp', label: 'Temp. Catalis.', unit: '°C', icon: 'fireplace' },
      { key: 'fuelTrimShort', label: 'Ajuste Curto', unit: '%', icon: 'tune' },
      { key: 'fuelTrimLong', label: 'Ajuste Longo', unit: '%', icon: 'tune-variant' },
      { key: 'fuelEfficiency', label: 'Eficiência', unit: ' km/L', icon: 'speedometer-slow' },
      { key: 'co2Emission', label: 'CO₂', unit: ' g/km', icon: 'smog' },
    ];

    const rendered = items.filter((item) => {
      const v = liveData[item.key];
      return v !== undefined && v !== null && v !== 'N/D' && !(typeof v === 'number' && Number.isNaN(v));
    });

    if (rendered.length === 0) {
      return <Text style={styles.noConditionText}>Nenhuma condição registrada neste scan.</Text>;
    }

    return (
      <View style={styles.conditionGrid}>
        {rendered.map((item) => (
          <View key={item.key} style={styles.conditionCard}>
            <MaterialCommunityIcons name={item.icon} size={18} color="#FFCF00" />
            <Text style={styles.conditionValue}>
              {liveData[item.key]}
              {item.unit}
            </Text>
            <Text style={styles.conditionLabel}>{item.label}</Text>
          </View>
        ))}
      </View>
    );
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
          <Text style={styles.headerTitle}>INFORMAÇÕES OBD</Text>
          {vehicle && (
            <Text style={styles.vehicleSubtitle}>
              {vehicle.brand} {vehicle.model} • {vehicle.year}
            </Text>
          )}
        </View>
        <TouchableOpacity
          onPress={() => fetchVehicleAndScans(true)}
          disabled={loading || refreshing}
          style={[styles.refreshButton, (loading || refreshing) && { opacity: 0.5 }]}
        >
          {refreshing ? (
            <ActivityIndicator size="small" color="#000" />
          ) : (
            <MaterialCommunityIcons name="refresh" size={22} color="#000" />
          )}
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={true}
      >
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2C2C2C" />
            <Text style={styles.loadingText}>Carregando histórico...</Text>
          </View>
        ) : !vehicle ? (
          <View style={styles.emptyState}>
            <FontAwesome5 name="car-crash" size={40} color="#CCC" />
            <Text style={styles.emptyStateText}>
              Nenhum veículo cadastrado. Cadastre um veículo para começar a registrar scanners.
            </Text>
          </View>
        ) : scans.length === 0 ? (
          <View style={styles.emptyState}>
            <MaterialCommunityIcons name="clipboard-text-search-outline" size={44} color="#CCC" />
            <Text style={styles.emptyStateText}>
              Nenhum registro de scanner ainda. Conecte o OBD e leia os códigos de erro para começar
              a gerar histórico.
            </Text>
          </View>
        ) : (
          scans.map((scan) => {
            const isExpanded = expandedId === scan.id;
            const hasErrors = scan.dtc_codes && scan.dtc_codes.length > 0;

            return (
              <TouchableOpacity
                key={scan.id}
                style={styles.scanCard}
                activeOpacity={0.8}
                onPress={() => toggleExpand(scan.id)}
              >
                <View style={styles.scanCardHeader}>
                  <View style={styles.scanCardHeaderLeft}>
                    <MaterialCommunityIcons
                      name={hasErrors ? 'alert-circle' : 'check-circle'}
                      size={22}
                      color={hasErrors ? '#FF5722' : '#4CAF50'}
                    />
                    <View style={styles.scanCardHeaderText}>
                      <Text style={styles.scanCardDate}>{formatDate(scan.scan_date)}</Text>
                      <Text style={styles.scanCardSummary}>
                        {hasErrors
                          ? `${scan.dtc_codes.length} código(s) encontrado(s)`
                          : 'Nenhum código de falha'}
                      </Text>
                    </View>
                  </View>
                  <Ionicons
                    name={isExpanded ? 'chevron-up' : 'chevron-down'}
                    size={20}
                    color="#999"
                  />
                </View>

                {isExpanded && (
                  <View style={styles.scanCardBody}>
                    <Text style={styles.sectionLabel}>Códigos de Erro</Text>
                    {hasErrors ? (
                      scan.dtc_codes.map((dtc, index) => (
                        <View key={index} style={styles.dtcRow}>
                          <View
                            style={[
                              styles.dtcSeverityDot,
                              { backgroundColor: severityColor(dtc.severity) }
                            ]}
                          />
                          <View style={styles.dtcRowText}>
                            <Text style={styles.dtcRowCode}>{dtc.code}</Text>
                            <Text style={styles.dtcRowDescription}>{dtc.description}</Text>
                          </View>
                        </View>
                      ))
                    ) : (
                      <Text style={styles.noErrorsText}>
                        Nenhum código de erro detectado neste scan.
                      </Text>
                    )}

                    <Text style={[styles.sectionLabel, { marginTop: 16 }]}>
                      Condições do Veículo no Momento
                    </Text>
                    {renderConditionGrid(scan.live_data)}

                    {scan.connected_device && (
                      <Text style={styles.deviceInfoText}>
                        Dispositivo: {scan.connected_device}
                      </Text>
                    )}
                    
                    <TouchableOpacity
                      style={styles.analyzeButton}
                      onPress={() => handleAnalyzeScan(scan.id)}
                      disabled={analyzingId === scan.id}
                    >
                      {analyzingId === scan.id ? (
                        <ActivityIndicator size="small" color="#FFCF00" />
                      ) : (
                        <MaterialCommunityIcons name="robot" size={20} color="#FFCF00" />
                      )}
                      <Text style={styles.analyzeButtonText}>
                        {analyzingId === scan.id ? 'Analisando...' : 'Analisar com IA'}
                      </Text>
                    </TouchableOpacity>
                    
                    {analysisData[scan.id] && (
                      <View style={styles.analysisContainer}>
                        <Text style={styles.sectionLabel}>Análise da IA</Text>
                        <Text style={styles.analysisText}>{analysisData[scan.id].analysis}</Text>
                        
                        {analysisData[scan.id].abnormal_values && analysisData[scan.id].abnormal_values.length > 0 && (
                          <>
                            <Text style={[styles.sectionLabel, { marginTop: 12 }]}>Valores Anômalos</Text>
                            {analysisData[scan.id].abnormal_values.map((item, idx) => (
                              <View key={idx} style={styles.abnormalValueItem}>
                                <Text style={styles.abnormalValueLabel}>{item.parameter}</Text>
                                <Text style={styles.abnormalValueText}>
                                  {item.current_value} (esperado: {item.expected_range})
                                </Text>
                                <Text style={styles.abnormalValueIssue}>{item.issue}</Text>
                              </View>
                            ))}
                          </>
                        )}
                        
                        {analysisData[scan.id].recommendations && analysisData[scan.id].recommendations.length > 0 && (
                          <>
                            <Text style={[styles.sectionLabel, { marginTop: 12 }]}>Recomendações</Text>
                            {analysisData[scan.id].recommendations.map((rec, idx) => (
                              <View key={idx} style={styles.recommendationItem}>
                                <View 
                                  style={[
                                    styles.recommendationPriorityDot, 
                                    { 
                                      backgroundColor: 
                                        rec.priority === 'alta' ? '#FF5722' : 
                                        rec.priority === 'média' ? '#FFC107' : '#8BC34A' 
                                    }
                                  ]} 
                                />
                                <View style={styles.recommendationText}>
                                  <Text style={styles.recommendationTitle}>{rec.title}</Text>
                                  <Text style={styles.recommendationDesc}>{rec.description}</Text>
                                </View>
                              </View>
                            ))}
                          </>
                        )}
                      </View>
                    )}
                  </View>
                )}
              </TouchableOpacity>
            );
          })
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>

      <BottomNav navigation={navigation} user={loggedUser} activeScreen="Home" />
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
  refreshButton: {
    width: 40,
    height: 40,
    marginLeft: 'auto',
    borderRadius: 20,
    backgroundColor: '#FFCF00',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'flex-start',
    zIndex: 2,
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
  vehicleSubtitle: {
    fontSize: 11,
    color: '#666',
    marginTop: 4,
    textAlign: 'center'
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
    paddingVertical: 50,
    paddingHorizontal: 20
  },
  emptyStateText: {
    marginTop: 14,
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    lineHeight: 20
  },
  scanCard: {
    backgroundColor: '#F7F7F7',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#EEEEEE'
  },
  scanCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  scanCardHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1
  },
  scanCardHeaderText: {
    marginLeft: 12,
    flex: 1
  },
  scanCardDate: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1A1A1A'
  },
  scanCardSummary: {
    fontSize: 12,
    color: '#777',
    marginTop: 2
  },
  scanCardBody: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E5E5'
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#555',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 10
  },
  dtcRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#EEEEEE'
  },
  dtcSeverityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 4,
    marginRight: 10
  },
  dtcRowText: {
    flex: 1
  },
  dtcRowCode: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1A1A1A'
  },
  dtcRowDescription: {
    fontSize: 12,
    color: '#777',
    marginTop: 2
  },
  noErrorsText: {
    fontSize: 13,
    color: '#4CAF50',
    fontStyle: 'italic'
  },
  conditionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between'
  },
  conditionCard: {
    width: '31%',
    backgroundColor: '#2E2E2E',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 10
  },
  conditionValue: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    marginTop: 6
  },
  conditionLabel: {
    color: '#AAAAAA',
    fontSize: 9,
    marginTop: 2,
    textAlign: 'center'
  },
  noConditionText: {
    fontSize: 12,
    color: '#999',
    fontStyle: 'italic'
  },
  deviceInfoText: {
    fontSize: 11,
    color: '#999',
    marginTop: 12,
    fontStyle: 'italic'
  },
  analyzeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2E2E2E',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginTop: 16
  },
  analyzeButtonText: {
    color: '#FFCF00',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 8
  },
  analysisContainer: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E5E5'
  },
  analysisText: {
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
    marginTop: 8
  },
  abnormalValueItem: {
    backgroundColor: '#FFF3CD',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8
  },
  abnormalValueLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#856404'
  },
  abnormalValueText: {
    fontSize: 12,
    color: '#856404',
    marginTop: 4
  },
  abnormalValueIssue: {
    fontSize: 12,
    color: '#856404',
    marginTop: 4,
    fontStyle: 'italic'
  },
  recommendationItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#E8F5E9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8
  },
  recommendationPriorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 4,
    marginRight: 12
  },
  recommendationText: {
    flex: 1
  },
  recommendationTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#155724'
  },
  recommendationDesc: {
    fontSize: 12,
    color: '#155724',
    marginTop: 4
  },
  bottomSpacer: {
    height: 60
  }
});

export default OBDHistoryScreen;
