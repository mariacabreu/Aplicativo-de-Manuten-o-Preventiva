import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
  ActivityIndicator,
  Image,
  Modal,
  PermissionsAndroid
} from 'react-native';
import { MaterialCommunityIcons, Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { useFocusEffect } from '@react-navigation/native';
import API_BASE_URL from '../api';
import BottomNav from '../components/NavBar/BottomNav';
import AMPAlertModal from '../components/Common/AMPAlertModal';

const OBD_CONNECTION_OPTIONS = {
  connectorType: 'rfcomm',
  connectionType: 'delimited',
  delimiter: '>',
  charset: 'utf-8',
  readSize: 2048,
  secureSocket: false,
};

const DTC_SYSTEM_MAP = ['P', 'C', 'B', 'U'];
const DTC_DESCRIPTION_MAP = {
  P0100: 'Falha no circuito do sensor MAF',
  P0101: 'Faixa/desempenho incorreto no sensor MAF',
  P0102: 'Sinal baixo no sensor MAF',
  P0103: 'Sinal alto no sensor MAF',
  P0104: 'Falha intermitente no sensor de fluxo de ar (MAF)',
  P0110: 'Falha no circuito do sensor de temperatura do ar de admissão',
  P0113: 'Sinal alto no sensor de temperatura do ar de admissão',
  P0120: 'Falha no circuito do sensor de posição da borboleta',
  P0130: 'Falha no circuito da sonda lambda (banco 1, sensor 1)',
  P0171: 'Mistura pobre detectada no banco 1',
  P0300: 'Falhas de ignição aleatórias detectadas',
  P0301: 'Falha de ignição detectada no cilindro 1',
  P0302: 'Falha de ignição detectada no cilindro 2',
  P0303: 'Falha de ignição detectada no cilindro 3',
  P0304: 'Falha de ignição detectada no cilindro 4',
  P0420: 'Eficiência do catalisador abaixo do limite',
};

const NOT_AVAILABLE = 'N/D';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const BluetoothClassic = (() => {
  if (Platform.OS !== 'android') {
    return null;
  }
  try {
    const module = require('react-native-bluetooth-classic');
    return module.default || module;
  } catch (e) {
    console.log('react-native-bluetooth-classic not available:', e.message);
    return null;
  }
})();

const OBDScreen = ({ navigation, route }) => {
  const loggedUser = route.params?.user;
  const [isConnected, setIsConnected] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [deviceList, setDeviceList] = useState([]);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [connectedDevice, setConnectedDevice] = useState(null);
  const [vehicle, setVehicle] = useState(null);
  const [isReading, setIsReading] = useState(false);
  const intervalRef = useRef(null);
  const connectionRef = useRef(null);
  const commandQueueRef = useRef(Promise.resolve());
  const supportedPidsRef = useRef(new Set());
  const lastSaveTimestampRef = useRef(0);
  const pendingSaveRef = useRef(null);
  const [alertModalVisible, setAlertModalVisible] = useState(false);
  const [alertModalData, setAlertModalData] = useState({
    type: 'info',
    title: '',
    message: '',
    confirmButtonText: 'Ok',
    onConfirm: () => setAlertModalVisible(false),
    cancelButtonText: 'Cancelar',
    onCancel: () => setAlertModalVisible(false),
  });

  const [liveData, setLiveData] = useState({
    rpm: NOT_AVAILABLE,
    speed: NOT_AVAILABLE,
    coolantTemp: NOT_AVAILABLE,
    fuelLevel: NOT_AVAILABLE,
    batteryVoltage: NOT_AVAILABLE,
    engineLoad: NOT_AVAILABLE,
    airIntakeTemp: NOT_AVAILABLE,
    throttlePosition: NOT_AVAILABLE,
    fuelPressure: NOT_AVAILABLE,
    intakeManifoldPressure: NOT_AVAILABLE,
    oilTemp: NOT_AVAILABLE,
    oilPressure: NOT_AVAILABLE,
    lambda: NOT_AVAILABLE,
    maf: NOT_AVAILABLE,
    timingAdvance: NOT_AVAILABLE,
    egr: NOT_AVAILABLE,
    evapSystemVaporPressure: NOT_AVAILABLE,
    fuelTrimShort: NOT_AVAILABLE,
    fuelTrimLong: NOT_AVAILABLE,
    catalystTemp: NOT_AVAILABLE,
    ambientTemp: NOT_AVAILABLE,
    fuelEfficiency: NOT_AVAILABLE,
    co2Emission: NOT_AVAILABLE
  });
  const [dtcCodes, setDtcCodes] = useState([]);
  const [isLoadingDTC, setIsLoadingDTC] = useState(false);

  useEffect(() => {
    fetchVehicleData();
  }, []);

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const fetchVehicleData = async () => {
    try {
      const userId = loggedUser?.id || 1;
      const response = await axios.get(`${API_BASE_URL}/user/status/${userId}`);
      if (response.data.vehicle) {
        setVehicle(response.data.vehicle);
      }
    } catch (error) {
      console.error('Erro ao buscar dados do veículo:', error);
    }
  };

  useFocusEffect(
    useCallback(() => {
      if (!loggedUser?.id) {
        return undefined;
      }

      fetchVehicleData();
      return undefined;
    }, [loggedUser?.id])
  );

  const requestBluetoothPermissions = async () => {
    if (Platform.OS === 'android') {
      try {
        const permissions = Platform.Version >= 31
          ? [
              PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
              PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
            ]
          : [PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION];

        const granted = await PermissionsAndroid.requestMultiple(permissions);

        const allGranted = Object.values(granted).every(
          (status) => status === PermissionsAndroid.RESULTS.GRANTED
        );

        return allGranted;
      } catch (err) {
        console.warn(err);
        return false;
      }
    }
    return true;
  };

  const normalizeElmResponse = (response, command = '') => {
    const commandUpper = command.toUpperCase().replace(/\s+/g, '');

    return String(response || '')
      .replace(/\0/g, '')
      .replace(/\r/g, '\n')
      .replace(/>/g, '\n')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((line) => {
        const lineUpper = line.toUpperCase().replace(/\s+/g, '');
        return lineUpper !== commandUpper && lineUpper !== 'SEARCHING...' && lineUpper !== 'NO DATA' && lineUpper !== 'OK';
      })
      .join(' ')
      .trim();
  };

  const extractResponseBytes = (response, expectedMode) => {
    const normalized = normalizeElmResponse(response).toUpperCase();
    const compactHex = normalized.replace(/[^0-9A-F]/g, '');

    if (compactHex.length < 2) {
      return null;
    }

    const bytes = [];
    for (let index = 0; index < compactHex.length - 1; index += 2) {
      bytes.push(parseInt(compactHex.slice(index, index + 2), 16));
    }

    if (bytes.length === 0) {
      return null;
    }

    let responseStartIndex = bytes.findIndex((byte) => byte === expectedMode);

    if (responseStartIndex === -1) {
      const commonModes = [0x41, 0x43, 0x42];
      for (const mode of commonModes) {
        const idx = bytes.findIndex((byte) => byte === mode);
        if (idx !== -1) {
          responseStartIndex = idx;
          break;
        }
      }
    }

    if (responseStartIndex === -1) {
      return bytes.length >= 2 ? bytes : null;
    }

    return bytes.slice(responseStartIndex);
  };

  const getGenericDTCDescription = (code) => {
    if (code.startsWith('P')) {
      return 'Falha detectada no conjunto motor/cambio.';
    }
    if (code.startsWith('C')) {
      return 'Falha detectada no sistema de chassis.';
    }
    if (code.startsWith('B')) {
      return 'Falha detectada no sistema de carroceria.';
    }
    if (code.startsWith('U')) {
      return 'Falha detectada na rede de comunicacao do veiculo.';
    }

    return 'Falha OBD-II detectada.';
  };

  const getDTCSeverity = (code) => {
    if (/^P0(3|2|1)/.test(code) || code === 'P0420') {
      return 'high';
    }

    return 'medium';
  };

  const decodeDTCBytes = (firstByte, secondByte) => {
    if (firstByte === 0 && secondByte === 0) {
      return null;
    }

    const system = DTC_SYSTEM_MAP[(firstByte & 0xC0) >> 6] || 'P';
    const code = [
      system,
      ((firstByte & 0x30) >> 4).toString(),
      (firstByte & 0x0F).toString(16).toUpperCase(),
      ((secondByte & 0xF0) >> 4).toString(16).toUpperCase(),
      (secondByte & 0x0F).toString(16).toUpperCase(),
    ].join('');

    return {
      code,
      description: DTC_DESCRIPTION_MAP[code] || getGenericDTCDescription(code),
      severity: getDTCSeverity(code),
    };
  };

  const parseDTCResponse = (response) => {
    const bytes = extractResponseBytes(response, 0x43);
    if (!bytes || bytes.length < 2) {
      return [];
    }

    const dtcPayload = bytes.slice(1);
    if (dtcPayload.length === 0 || dtcPayload.every((byte) => byte === 0)) {
      return [];
    }

    const dtcList = [];

    for (let index = 0; index < dtcPayload.length; index += 2) {
      const firstByte = dtcPayload[index];
      const secondByte = dtcPayload[index + 1] ?? 0;
      const decoded = decodeDTCBytes(firstByte, secondByte);

      if (decoded) {
        dtcList.push(decoded);
      }
    }

    return dtcList;
  };

  const isPidSupported = (pidHex) => {
    return supportedPidsRef.current.has(pidHex.toUpperCase());
  };

  const parseSupportedPids = (bytes) => {
    if (!bytes || bytes.length < 4) return;
    const dataBytes = bytes.slice(2, 6);
    const supported = new Set();
    const pids01To20 = [
      '0101','0102','0103','0104','0105','0106','0107','0108',
      '0109','010A','010B','010C','010D','010E','010F','0110',
      '0111','0112','0113','0114','0115','0116','0117','0118',
      '0119','011A','011B','011C','011D','011E','011F','0120'
    ];
    const pids21To40 = [
      '0121','0122','0123','0124','0125','0126','0127','0128',
      '0129','012A','012B','012C','012D','012E','012F','0130',
      '0131','0132','0133','0134','0135','0136','0137','0138',
      '0139','013A','013B','013C','013D','013E','013F','0140'
    ];
    const pids41To60 = [
      '0141','0142','0143','0144','0145','0146','0147','0148',
      '0149','014A','014B','014C','014D','014E','014F','0150',
      '0151','0152','0153','0154','0155','0156','0157','0158',
      '0159','015A','015B','015C','015D','015E','015F','0160'
    ];

    let pidList;
    const responsePid = bytes[1] ? bytes[1].toString(16).padStart(2, '0').toUpperCase() : '';
    if (responsePid === '00') pidList = pids01To20;
    else if (responsePid === '20') pidList = pids21To40;
    else if (responsePid === '40') pidList = pids41To60;
    else return;

    let bitIndex = 0;
    for (const byte of dataBytes) {
      for (let bit = 7; bit >= 0; bit--) {
        if (byte & (1 << bit)) {
          const pidCode = pidList[bitIndex];
          if (pidCode) supported.add(pidCode);
        }
        bitIndex++;
      }
    }
    return supported;
  };

  const sendOBDCommand = async (command, options = {}) => {
    if (!connectionRef.current || !BluetoothClassic) {
      throw new Error('Não conectado a nenhum dispositivo');
    }

    const {
      clearBuffer = true,
      waitAfterWriteMs = 350,
      readAttempts = 3,
    } = options;

    const normalizedCommand = command.replace(/\s+/g, '').toUpperCase();

    const runCommand = async () => {
      try {
        if (clearBuffer) {
          await connectionRef.current.clear().catch(() => false);
        }

        await connectionRef.current.write(`${normalizedCommand}\r`, 'utf-8');
        await delay(waitAfterWriteMs);

        let response = '';
        for (let attempt = 0; attempt < readAttempts; attempt += 1) {
          const chunk = await connectionRef.current.read().catch(() => '');
          if (chunk) {
            response = `${response}\n${chunk}`.trim();
          }

          const remainingMessages = await connectionRef.current.available().catch(() => 0);
          if (remainingMessages <= 0) {
            break;
          }

          await delay(180);
        }

        const cleanedResponse = normalizeElmResponse(response, normalizedCommand);
        return cleanedResponse;
      } catch (err) {
        console.error(`Erro no comando ${normalizedCommand}:`, err);
        throw err;
      }
    };

    const queuedCommand = commandQueueRef.current
      .catch(() => undefined)
      .then(runCommand);

    commandQueueRef.current = queuedCommand.catch(() => undefined);

    return queuedCommand;
  };

  const parseOBDResponse = (response, expectedMode = 0x41) => {
    if (!response || response.includes('NO DATA') || response.includes('?')) {
      return null;
    }

    const result = extractResponseBytes(response, expectedMode);
    return result;
  };

  const initializeOBDDevice = async () => {
    try {
      console.log('Inicializando ELM327...');

      const initCommands = [
        'ATZ',
        'ATE0',
        'ATL0',
        'ATS0',
        'ATH0',
        'ATSP0',
        'ATST32',
        'ATAT1',
        'ATCRA000',
      ];

      for (const cmd of initCommands) {
        try {
          await sendOBDCommand(cmd, {
            waitAfterWriteMs: cmd === 'ATZ' ? 2000 : 400,
            readAttempts: cmd === 'ATZ' ? 5 : 3,
          });
          await delay(cmd === 'ATZ' ? 1500 : 250);
        } catch (err) {
          console.log(`Comando ${cmd} falhou, continuando...`);
        }
      }

      try {
        const resp0100 = await sendOBDCommand('0100', {
          waitAfterWriteMs: 600,
          readAttempts: 4,
        });
        const bytes0100 = parseOBDResponse(resp0100);
        if (bytes0100) {
          const s1 = parseSupportedPids(bytes0100);
          if (s1) s1.forEach(p => supportedPidsRef.current.add(p));
        }
        await delay(400);

        try {
          const resp0120 = await sendOBDCommand('0120', {
            waitAfterWriteMs: 500,
            readAttempts: 3,
          });
          const bytes0120 = parseOBDResponse(resp0120);
          if (bytes0120) {
            const s2 = parseSupportedPids(bytes0120);
            if (s2) s2.forEach(p => supportedPidsRef.current.add(p));
          }
          await delay(300);

          const resp0140 = await sendOBDCommand('0140', {
            waitAfterWriteMs: 500,
            readAttempts: 3,
          });
          const bytes0140 = parseOBDResponse(resp0140);
          if (bytes0140) {
            const s3 = parseSupportedPids(bytes0140);
            if (s3) s3.forEach(p => supportedPidsRef.current.add(p));
          }
        } catch (e) {
          console.log('Query de PIDs avançados falhou, seguindo sem eles');
        }
      } catch (err) {
        console.log('0100 falhou, mas continuando');
      }

      console.log('ELM327 inicializado com sucesso! PIDs suportados:', Array.from(supportedPidsRef.current));
      return true;
    } catch (err) {
      console.error('Erro geral ao inicializar OBD:', err);
      return false;
    }
  };

  const readBatteryVoltageFromELM = async () => {
    try {
      const resp = await sendOBDCommand('ATRV', {
        waitAfterWriteMs: 400,
        readAttempts: 3,
      });
      if (resp) {
        const match = String(resp).match(/(\d+\.?\d*)/);
        if (match) {
          return parseFloat(parseFloat(match[1]).toFixed(1));
        }
      }
    } catch (e) {
      console.log('ATRV falhou, tentando por PID...');
    }
    return null;
  };

  const calculateDerivedData = (data) => {
    const result = { ...data };

    const maf = result.maf;
    const speed = result.speed;
    if (typeof maf === 'number' && maf > 0 && typeof speed === 'number' && speed > 0) {
      const airFuelRatio = 14.7;
      const fuelGramPerSec = maf / airFuelRatio;
      const fuelLitersPerHour = (fuelGramPerSec * 3600) / 750;
      const kmPerHour = speed;
      if (fuelLitersPerHour > 0) {
        result.fuelEfficiency = parseFloat((kmPerHour / fuelLitersPerHour).toFixed(1));
      }
    }

    if (typeof result.fuelEfficiency === 'number' && result.fuelEfficiency > 0) {
      const co2PerLiter = 2392;
      result.co2Emission = Math.round(co2PerLiter / result.fuelEfficiency);
    }

    return result;
  };

  const readLiveDataFromOBD = async () => {
    if (!isConnected || isReading) return;

    setIsReading(true);
    try {
      if (!connectionRef.current) {
        throw new Error('Não conectado a um dispositivo OBD');
      }

      let gotRealData = false;
      const newData = { ...liveData };

      const readPid = async (cmd, parser, pidHex = null) => {
        try {
          if (pidHex && !isPidSupported(pidHex)) {
            return;
          }
          const resp = await sendOBDCommand(cmd, {
            waitAfterWriteMs: 350,
            readAttempts: 3,
          });
          const bytes = parseOBDResponse(resp);
          if (bytes && bytes.length >= 2) {
            const parsedValues = parser(bytes);
            if (parsedValues && typeof parsedValues === 'object') {
              Object.assign(newData, parsedValues);
              gotRealData = true;
            }
          }
        } catch (err) {
          console.log(`Erro ao ler PID ${cmd}:`, err?.message || err);
        }
      };

      await readPid('0104', b => ({ engineLoad: Math.round((b[2] * 100) / 255) }), '0104');
      await readPid('0105', b => ({ coolantTemp: b[2] - 40 }), '0105');
      await readPid('0106', b => ({ fuelTrimShort: parseFloat(((b[2] - 128) * 100 / 128).toFixed(1)) }), '0106');
      await readPid('0107', b => ({ fuelTrimLong: parseFloat(((b[2] - 128) * 100 / 128).toFixed(1)) }), '0107');
      await readPid('010A', b => ({ fuelPressure: b[2] * 3 }), '010A');
      await readPid('010B', b => ({ intakeManifoldPressure: b[2] }), '010B');
      await readPid('010C', b => ({ rpm: Math.round(((b[2] * 256 + b[3]) / 4)) }), '010C');
      await readPid('010D', b => ({ speed: b[2] }), '010D');
      await readPid('010E', b => ({ timingAdvance: parseFloat(((b[2] / 2) - 64).toFixed(1)) }), '010E');
      await readPid('010F', b => ({ airIntakeTemp: b[2] - 40 }), '010F');
      await readPid('0110', b => ({ maf: parseFloat(((b[2] * 256 + b[3]) / 100).toFixed(2)) }), '0110');
      await readPid('0111', b => ({ throttlePosition: Math.round((b[2] * 100) / 255) }), '0111');
      await readPid('012C', b => ({ egr: Math.round((b[2] * 100) / 255) }), '012C');
      await readPid('012F', b => ({ fuelLevel: Math.round((b[2] * 100) / 255) }), '012F');
      await readPid('0132', b => ({ evapSystemVaporPressure: parseFloat((((b[2] * 256) + b[3]) / 4).toFixed(1)) }), '0132');
      await readPid('0134', b => {
        if (b.length >= 5) {
          const lambda = parseFloat(((b[2] * 256 + b[3]) / 32768).toFixed(3));
          return { lambda };
        }
        return null;
      }, '0134');
      await readPid('013C', b => ({ catalystTemp: Math.round(((b[2] * 256 + b[3]) / 10) - 40) }), '013C');
      await readPid('0142', b => ({ batteryVoltage: parseFloat(((b[2] * 256 + b[3]) / 1000).toFixed(1)) }), '0142');
      await readPid('0146', b => ({ ambientTemp: b[2] - 40 }), '0146');
      await readPid('015C', b => ({ oilTemp: b[2] - 40 }), '015C');

      const elmVoltage = await readBatteryVoltageFromELM();
      if (elmVoltage !== null) {
        newData.batteryVoltage = elmVoltage;
        gotRealData = true;
      }

      const finalData = calculateDerivedData(newData);

      if (gotRealData) {
        setLiveData(finalData);
        if (vehicle?.id) {
          const snapshotToSend = { ...finalData };
          throttledSaveLive([], snapshotToSend, { minIntervalMs: 30000 });
        }
      }
    } catch (err) {
      console.error('Erro ao ler dados OBD:', err);
    } finally {
      setIsReading(false);
    }
  };

  const readDTCFromOBD = async () => {
    setIsLoadingDTC(true);
    try {
      if (!connectionRef.current) {
        setAlertModalData({
          type: 'error',
          title: 'Erro',
          message: 'Não conectado a um dispositivo OBD',
          confirmButtonText: 'Ok',
          onConfirm: () => setAlertModalVisible(false),
        });
        setAlertModalVisible(true);
        return;
      }

      const resp = await sendOBDCommand('03', {
        waitAfterWriteMs: 700,
        readAttempts: 4,
      });
      const codes = parseDTCResponse(resp);

      setDtcCodes(codes);
      if (vehicle?.id) {
        const currentLiveSnapshot = {};
        Object.keys(liveData).forEach((k) => {
          const v = liveData[k];
          if (v !== 'N/D' && v !== null && v !== undefined) {
            currentLiveSnapshot[k] = v;
          }
        });
        saveOBDScanRecord(codes, currentLiveSnapshot);
      }
    } catch (err) {
      console.error('Erro ao ler DTCs:', err);
      setDtcCodes([]);
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: 'Falha ao ler códigos de erro',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
    } finally {
      setIsLoadingDTC(false);
    }
  };
  const saveOBDScanRecord = async (dtcList, liveDataSnapshot) => {
    if (!vehicle?.id) return;
    try {
      const liveDataToSend = {};
      const sourceData = liveDataSnapshot || liveData;
      const SENTINEL = 'N/D';
      if (!sourceData) {
      } else if (Array.isArray(sourceData)) {
      } else {
        Object.keys(sourceData).forEach((k) => {
          const v = sourceData[k];
          if (v !== SENTINEL && v !== null && v !== undefined && !Number.isNaN(Number(v) ? Number.isNaN(v) : false)) {
            liveDataToSend[k] = v;
          }
        });
      }
      const payload = {
        vehicle_id: vehicle.id,
        scan_date: new Date().toISOString(),
        dtc_codes: Array.isArray(dtcList) ? dtcList : [],
        live_data: liveDataToSend,
        connected_device: connectedDevice?.name || null,
      };
      await axios.post(`${API_BASE_URL}/vehicle/obd-scan`, payload, {
        timeout: 15000,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (err) {
      console.error('Erro ao salvar registro de scanner:', err?.message || err);
    }
  };

  const throttledSaveLive = (dtcList, liveDataSnapshot, { minIntervalMs = 30000, force = false } = {}) => {
    const now = Date.now();
    const dtcCodesArr = Array.isArray(dtcList) ? dtcList : [];
    const hasDTC = dtcCodesArr.length > 0;
    if (!force && !hasDTC) {
      if (now - lastSaveTimestampRef.current < minIntervalMs) {
        pendingSaveRef.current = { dtcList: dtcCodesArr, liveDataSnapshot, timestamp: now };
        return;
      }
    }
    lastSaveTimestampRef.current = now;
    if (pendingSaveRef.current) {
      pendingSaveRef.current = null;
    }
    saveOBDScanRecord(dtcCodesArr, liveDataSnapshot || (pendingSaveRef.current?.liveDataSnapshot));
  };

  const handleScanDevices = async () => {
    if (Platform.OS !== 'android') {
      setAlertModalData({
        type: 'info',
        title: 'Plataforma Não Suportada',
        message: 'A conexão com scanner OBD2 é suportada apenas em dispositivos Android.',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
      return;
    }

    const hasPermissions = await requestBluetoothPermissions();

    if (!hasPermissions) {
      setAlertModalData({
        type: 'error',
        title: 'Permissão Negada',
        message: 'As permissões de Bluetooth são necessárias para conectar.',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
      return;
    }

    try {
      const bluetoothEnabled = await BluetoothClassic?.isBluetoothEnabled?.();
      if (!bluetoothEnabled) {
        await BluetoothClassic?.requestBluetoothEnabled?.();
      }
    } catch (err) {
      console.log('Não foi possível solicitar ativação do Bluetooth:', err?.message || err);
    }

    setIsScanning(true);
    setDeviceList([]);

    try {
      if (BluetoothClassic) {
        const devices = await BluetoothClassic.getBondedDevices();
        const looksLikeOBD = (name = '') => {
          const normalizedName = name.toLowerCase();
          return normalizedName.includes('obd')
            || normalizedName.includes('elm')
            || normalizedName.includes('scan')
            || normalizedName.includes('v-link')
            || normalizedName.includes('vlink');
        };

        const prioritizedDevices = [
          ...devices.filter((device) => looksLikeOBD(device.name)),
          ...devices.filter((device) => !looksLikeOBD(device.name)),
        ];

        setDeviceList(
          prioritizedDevices.map((device) => ({
            id: device.address,
            name: device.name || 'Dispositivo sem nome',
            address: device.address,
          }))
        );
      } else {
        setAlertModalData({
          type: 'error',
          title: 'Erro',
          message: 'Biblioteca de Bluetooth não disponível.',
          confirmButtonText: 'Ok',
          onConfirm: () => setAlertModalVisible(false),
        });
        setAlertModalVisible(true);
      }
    } catch (err) {
      console.error('Erro ao buscar dispositivos:', err);
      setAlertModalData({
        type: 'error',
        title: 'Erro',
        message: 'Falha ao buscar dispositivos Bluetooth',
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
    } finally {
      setIsScanning(false);
    }
  };

  const handleConnectDevice = async (device) => {
    try {
      const connection = await BluetoothClassic.connectToDevice(device.address, OBD_CONNECTION_OPTIONS);
      connectionRef.current = connection;
      supportedPidsRef.current = new Set();

      const initialized = await initializeOBDDevice();
      if (!initialized) {
        throw new Error('Falha ao inicializar o ELM327');
      }

      setIsConnected(true);
      setConnectedDevice(device);
      setShowDashboard(true);

      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }

      lastSaveTimestampRef.current = 0;
      pendingSaveRef.current = null;

      await readLiveDataFromOBD();
      if (vehicle?.id) {
        const freshLive = {};
        Object.entries(liveData).forEach(([k, v]) => {
          if (v !== 'N/D' && v !== null && v !== undefined) freshLive[k] = v;
        });
        if (Object.keys(freshLive).length > 0) {
          throttledSaveLive([], freshLive, { force: true });
        }
      }

      intervalRef.current = setInterval(() => {
        readLiveDataFromOBD();
      }, 2500);

      setAlertModalData({
        type: 'success',
        title: 'Conectado!',
        message: `Conectado com sucesso a ${device.name}`,
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
    } catch (err) {
      console.error('Erro ao conectar:', err);
      setAlertModalData({
        type: 'error',
        title: 'Erro de Conexão',
        message: `Falha ao conectar a ${device.name}.\n\nVerifique se o dispositivo está pareado corretamente e se o PIN foi digitado corretamente (1234, 0000, 7890 ou 1111).`,
        confirmButtonText: 'Ok',
        onConfirm: () => setAlertModalVisible(false),
      });
      setAlertModalVisible(true);
    }
  };

  const handleDisconnect = async () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (vehicle?.id && isConnected) {
      try {
        const lastSnapshot = {};
        Object.entries(liveData).forEach(([k, v]) => {
          if (v !== 'N/D' && v !== null && v !== undefined) lastSnapshot[k] = v;
        });
        const lastDTC = Array.isArray(dtcCodes) ? dtcCodes : [];
        if (Object.keys(lastSnapshot).length > 0 || lastDTC.length > 0) {
          saveOBDScanRecord(lastDTC, lastSnapshot);
        }
      } catch (e) {
        console.warn('Erro ao salvar último snapshot antes de desconectar:', e?.message || e);
      }
    }

    pendingSaveRef.current = null;
    lastSaveTimestampRef.current = 0;

    if (connectionRef.current) {
      try {
        await connectionRef.current.disconnect();
      } catch (err) {
        console.error('Erro ao desconectar:', err);
      }
      connectionRef.current = null;
    }

    setIsConnected(false);
    setShowDashboard(false);
    setDeviceList([]);
    setConnectedDevice(null);
    supportedPidsRef.current = new Set();

    setAlertModalData({
      type: 'info',
      title: 'Desconectado',
      message: 'Dispositivo desconectado!',
      confirmButtonText: 'Ok',
      onConfirm: () => setAlertModalVisible(false),
    });
    setAlertModalVisible(true);
  };

  const renderValue = (value, suffix = '') => {
    if (value === NOT_AVAILABLE || value === null || value === undefined) {
      return <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>;
    }
    return <Text style={styles.dataCardValue}>{value}{suffix}</Text>;
  };

  const renderGaugeValue = (value, suffix = '') => {
    if (value === NOT_AVAILABLE || value === null || value === undefined) {
      return <Text style={styles.gaugeValueNA}>{NOT_AVAILABLE}</Text>;
    }
    return (
      <>
        <Text style={styles.gaugeValue}>{value}</Text>
        {suffix ? <Text style={styles.gaugeUnit}>{suffix}</Text> : null}
      </>
    );
  };

  const renderLargeValue = (value, suffix = '') => {
    if (value === NOT_AVAILABLE || value === null || value === undefined) {
      return <Text style={styles.consumptionValueNA}>{NOT_AVAILABLE}</Text>;
    }
    return (
      <>
        <Text style={styles.consumptionValue}>{value}</Text>
        {suffix ? <Text style={styles.consumptionUnit}>{suffix}</Text> : null}
      </>
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
            source={require('../assets/logo.png')}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <Text style={styles.headerTitle}>DIAGNÓSTICO EM TEMPO REAL</Text>
          {vehicle && (
            <Text style={styles.vehicleSubtitle}>
              {vehicle.brand} {vehicle.model} • {vehicle.year} • {vehicle.engine_type} • {vehicle.transmission}
            </Text>
          )}
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={true}
        scrollEnabled={true}
        nestedScrollEnabled={true}
        overScrollMode="always"
      >
        <View style={styles.statusHelpRow}>
          <View style={styles.statusContainerCentered}>
            <View style={[styles.statusDot, isConnected ? styles.statusDotConnected : styles.statusDotDisconnected]} />
            <Text style={[styles.statusText, isConnected ? styles.statusTextConnected : styles.statusTextDisconnected]}>
              {isConnected ? 'Conectado' : 'Desconectado'}
            </Text>
          </View>
          <View style={{ flexDirection: 'row' }}>
            <TouchableOpacity
              style={[styles.helpButton, { marginRight: 8 }]}
              onPress={() => navigation.navigate('OBDHistory', { user: loggedUser })}
            >
              <MaterialCommunityIcons name="history" size={20} color="#FFCF00" />
            </TouchableOpacity>
            <TouchableOpacity style={styles.helpButton} onPress={() => setShowHelp(true)}>
              <MaterialCommunityIcons name="help-circle" size={20} color="#FFCF00" />
            </TouchableOpacity>
          </View>
        </View>

        {!showDashboard && (
          <View style={styles.buttonsRow}>
            <TouchableOpacity style={styles.connectButton} onPress={handleScanDevices}>
              <MaterialCommunityIcons name="bluetooth-connect" size={22} color="#FFCF00" />
              <Text style={styles.connectButtonText}>
                CONECTAR
                <Text style={styles.connectButtonSubText}> OBD</Text>
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {showDashboard && (
          <View style={styles.dashboardContainer}>
            <View style={styles.obdPanel}>
              <View style={styles.panelHeader}>
                <MaterialCommunityIcons name="speedometer" size={28} color="#FFCF00" />
                <Text style={styles.panelTitle}>DADOS EM TEMPO REAL</Text>
              </View>

              <View style={styles.mainGaugesRow}>
                <View style={styles.gaugeItem}>
                  <MaterialCommunityIcons name="tachometer-slow" size={40} color="#FFCF00" />
                  {liveData.rpm === NOT_AVAILABLE ? (
                    <Text style={styles.gaugeValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <>
                      <Text style={styles.gaugeValue}>{liveData.rpm}</Text>
                      <Text style={styles.gaugeUnit}>RPM</Text>
                    </>
                  )}
                </View>
                <View style={styles.gaugeItem}>
                  <MaterialCommunityIcons name="speedometer" size={40} color="#FFCF00" />
                  {liveData.speed === NOT_AVAILABLE ? (
                    <Text style={styles.gaugeValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <>
                      <Text style={styles.gaugeValue}>{liveData.speed}</Text>
                      <Text style={styles.gaugeUnit}>KM/H</Text>
                    </>
                  )}
                </View>
                <View style={styles.gaugeItem}>
                  <MaterialCommunityIcons name="thermometer" size={40} color="#FFCF00" />
                  {liveData.coolantTemp === NOT_AVAILABLE ? (
                    <Text style={styles.gaugeValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <>
                      <Text style={styles.gaugeValue}>{liveData.coolantTemp}°C</Text>
                      <Text style={styles.gaugeUnit}>TEMPERATURA</Text>
                    </>
                  )}
                </View>
              </View>

              <View style={styles.dataGrid}>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="gas-station" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Combustível</Text>
                  {liveData.fuelLevel === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.fuelLevel}%</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="car-battery" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Carga do Motor</Text>
                  {liveData.engineLoad === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.engineLoad}%</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="gauge" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Pressão Coletor</Text>
                  {liveData.intakeManifoldPressure === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.intakeManifoldPressure} kPa</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="engine" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Posição Acelerador</Text>
                  {liveData.throttlePosition === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.throttlePosition}%</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="oil" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Temp. Ar Admissão</Text>
                  {liveData.airIntakeTemp === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.airIntakeTemp}°C</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="water" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Temp. Ambiente</Text>
                  {liveData.ambientTemp === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.ambientTemp}°C</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="car-battery" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Tensão Bateria</Text>
                  {liveData.batteryVoltage === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.batteryVoltage} V</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="weather-windy" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Fluxo de Ar (MAF)</Text>
                  {liveData.maf === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.maf} g/s</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="fire" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Pressão Combustível</Text>
                  {liveData.fuelPressure === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.fuelPressure} kPa</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="thermometer-lines" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Temp. Óleo Motor</Text>
                  {liveData.oilTemp === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.oilTemp}°C</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="omega" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Sonda Lambda</Text>
                  {liveData.lambda === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.lambda} λ</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="clock-fast" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Avanço Ignição</Text>
                  {liveData.timingAdvance === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.timingAdvance}°</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="valve" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>EGR</Text>
                  {liveData.egr === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.egr}%</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="waves" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Pressão Evap.</Text>
                  {liveData.evapSystemVaporPressure === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.evapSystemVaporPressure} Pa</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="fireplace" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Temp. Catalisador</Text>
                  {liveData.catalystTemp === NOT_AVAILABLE ? (
                    <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.dataCardValue}>{liveData.catalystTemp}°C</Text>
                  )}
                </View>
                <View style={styles.dataCard}>
                  <MaterialCommunityIcons name="filter-variant" size={22} color="#FFCF00" />
                  <Text style={styles.dataCardLabel}>Pressão Óleo</Text>
                  <Text style={styles.dataCardValueNA}>{NOT_AVAILABLE}</Text>
                </View>
              </View>
            </View>

            <View style={styles.obdPanel}>
              <View style={styles.panelHeader}>
                <MaterialCommunityIcons name="alert-circle" size={28} color="#FFCF00" />
                <Text style={styles.panelTitle}>DIAGNÓSTICO DE FALHAS</Text>
              </View>

              {dtcCodes.length > 0 ? (
                <View>
                  <View style={styles.dtcHeader}>
                    <Text style={styles.dtcCount}>{dtcCodes.length} Códigos Encontrados</Text>
                  </View>

                  {dtcCodes.map((dtc, index) => (
                    <View key={index} style={styles.dtcItem}>
                      <View style={[styles.dtcSeverity, { backgroundColor: dtc.severity === 'high' ? '#FF5722' : '#FFC107' }]} />
                      <View style={styles.dtcInfo}>
                        <Text style={styles.dtcCode}>{dtc.code}</Text>
                        <Text style={styles.dtcDescription}>{dtc.description}</Text>
                      </View>
                    </View>
                  ))}
                </View>
              ) : (
                <View style={styles.noDtcContainer}>
                  <MaterialCommunityIcons name="check-circle" size={48} color="#4CAF50" />
                  <Text style={styles.noDtcText}>Nenhum código de falha detectado</Text>
                </View>
              )}

              <TouchableOpacity style={styles.readDtcBtn} onPress={readDTCFromOBD}>
                {isLoadingDTC ? (
                  <ActivityIndicator size="small" color="#FFCF00" />
                ) : (
                  <MaterialCommunityIcons name="refresh" size={20} color="#FFCF00" />
                )}
                <Text style={styles.readDtcText}>{isLoadingDTC ? 'Lendo códigos...' : 'Ler Códigos de Erro'}</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.obdPanel}>
              <View style={styles.panelHeader}>
                <MaterialCommunityIcons name="chart-line" size={28} color="#FFCF00" />
                <Text style={styles.panelTitle}>CONSUMO E EMISSÕES</Text>
              </View>

              <View style={styles.consumptionGrid}>
                <View style={styles.consumptionCard}>
                  <MaterialCommunityIcons name="speedometer" size={32} color="#FFCF00" />
                  {liveData.fuelEfficiency === NOT_AVAILABLE ? (
                    <>
                      <Text style={styles.consumptionValueNA}>{NOT_AVAILABLE}</Text>
                      <Text style={styles.consumptionLabel}>Eficiência</Text>
                    </>
                  ) : (
                    <>
                      <Text style={styles.consumptionValue}>{liveData.fuelEfficiency}</Text>
                      <Text style={styles.consumptionUnit}>KM/L</Text>
                      <Text style={styles.consumptionLabel}>Eficiência</Text>
                    </>
                  )}
                </View>
                <View style={styles.consumptionCard}>
                  <MaterialCommunityIcons name="smog" size={32} color="#FFCF00" />
                  {liveData.co2Emission === NOT_AVAILABLE ? (
                    <>
                      <Text style={styles.consumptionValueNA}>{NOT_AVAILABLE}</Text>
                      <Text style={styles.consumptionLabel}>Emissões CO₂</Text>
                    </>
                  ) : (
                    <>
                      <Text style={styles.consumptionValue}>{liveData.co2Emission}</Text>
                      <Text style={styles.consumptionUnit}>G/KM</Text>
                      <Text style={styles.consumptionLabel}>Emissões CO₂</Text>
                    </>
                  )}
                </View>
              </View>

              <View style={styles.fuelTrimsRow}>
                <View style={styles.fuelTrimItem}>
                  <Text style={styles.fuelTrimLabel}>Ajuste Curto</Text>
                  {liveData.fuelTrimShort === NOT_AVAILABLE ? (
                    <Text style={styles.fuelTrimValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.fuelTrimValue}>{liveData.fuelTrimShort}%</Text>
                  )}
                </View>
                <View style={styles.fuelTrimItem}>
                  <Text style={styles.fuelTrimLabel}>Ajuste Longo</Text>
                  {liveData.fuelTrimLong === NOT_AVAILABLE ? (
                    <Text style={styles.fuelTrimValueNA}>{NOT_AVAILABLE}</Text>
                  ) : (
                    <Text style={styles.fuelTrimValue}>{liveData.fuelTrimLong}%</Text>
                  )}
                </View>
              </View>
            </View>

            {isConnected && (
              <View style={styles.actionButtonsContainer}>
                <TouchableOpacity style={styles.actionButton} onPress={readLiveDataFromOBD}>
                  <MaterialCommunityIcons name="refresh" size={24} color="#FFCF00" />
                  <Text style={styles.actionButtonText}>Atualizar Dados</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.actionButton, styles.actionButtonDanger]} onPress={handleDisconnect}>
                  <MaterialCommunityIcons name="bluetooth-off" size={24} color="#FFFFFF" />
                  <Text style={styles.actionButtonTextWhite}>Desconectar</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}

        {!showDashboard && (
          <View style={styles.connectionSection}>
            {isScanning && (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#FFCF00" />
                <Text style={styles.loadingText}>Procurando dispositivos...</Text>
              </View>
            )}
            {deviceList.length > 0 && !isConnected && (
              <View style={styles.deviceListContainer}>
                <Text style={styles.deviceListTitle}>Dispositivos Encontrados:</Text>
                {deviceList.map((device) => (
                  <TouchableOpacity
                    key={device.id}
                    style={styles.deviceItem}
                    onPress={() => handleConnectDevice(device)}
                  >
                    <MaterialCommunityIcons name="car-connected" size={28} color="#FFCF00" />
                    <View style={styles.deviceInfo}>
                      <Text style={styles.deviceName}>{device.name}</Text>
                      <Text style={styles.deviceAddress}>{device.address}</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={24} color="#999" />
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>

      <Modal
        animationType="slide"
        transparent={true}
        visible={showHelp}
        onRequestClose={() => setShowHelp(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Como Conectar o Scanner OBD2</Text>
              <TouchableOpacity style={styles.closeButton} onPress={() => setShowHelp(false)}>
                <MaterialCommunityIcons name="close" size={28} color="#333" />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalScroll}>
              <View style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>1</Text>
                </View>
                <Text style={styles.stepText}>
                  Localize a porta OBD2 do seu veículo {vehicle ? `(${vehicle.brand} ${vehicle.model} ${vehicle.year}, geralmente está embaixo do painel de instrumentos, lado do motorista)` : '(geralmente está embaixo do painel de instrumentos, lado do motorista)'}
                </Text>
              </View>
              <View style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>2</Text>
                </View>
                <Text style={styles.stepText}>
                  Com o carro ligado na chave (ignição ligada), espete o scanner na porta.
                </Text>
              </View>
              <View style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>3</Text>
                </View>
                <Text style={styles.stepText}>
                  Vá nas configurações Bluetooth do seu celular, pareie com o dispositivo OBD2 (nome geralmente começa com OBDII, OBD2 ou ELM327).
                </Text>
              </View>
              <View style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>4</Text>
                </View>
                <Text style={styles.stepText}>
                  Se pedir PIN, tente: 1234, 0000, 7890 ou 1111.
                </Text>
              </View>
              <View style={styles.stepItem}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>5</Text>
                </View>
                <Text style={styles.stepText}>
                  Volte para este app e clique em "CONECTAR OBD" para conectar com o dispositivo pareado.
                </Text>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      <BottomNav navigation={navigation} user={loggedUser} activeScreen="Home" />

      <AMPAlertModal
        visible={alertModalVisible}
        type={alertModalData.type}
        title={alertModalData.title}
        message={alertModalData.message}
        confirmButtonText={alertModalData.confirmButtonText}
        cancelButtonText={alertModalData.cancelButtonText}
        onConfirm={alertModalData.onConfirm}
        onCancel={alertModalData.onCancel}
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
    paddingBottom: 50,
    backgroundColor: '#fff',
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#000',
    marginTop: 6,
    letterSpacing: 0.5,
  },
  vehicleSubtitle: {
    fontSize: 11,
    color: '#666',
    marginTop: 4,
    textAlign: 'center',
  },
  backButton: {
    width: 40,
    zIndex: 2,
    alignSelf: 'flex-start',
  },
  logoContainer: {
    position: 'absolute',
    top: 40,
    bottom: 16,
    left: 0,
    right: 0,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerLogo: {
    width: 120,
    height: 60,
  },
  iconButton: {
    marginLeft: 10,
    padding: 4
  },
  topIcon: {
    width: 24,
    height: 24
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
    paddingBottom: 100,
    alignItems: 'center'
  },
  statusHelpRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    marginBottom: 12,
    width: '100%'
  },
  statusContainerCentered: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#F5F5F5',
    borderRadius: 24
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8
  },
  statusDotConnected: {
    backgroundColor: '#4CAF50'
  },
  statusDotDisconnected: {
    backgroundColor: '#F44336'
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
    fontFamily: 'Inter, sans-serif'
  },
  statusTextConnected: {
    color: '#4CAF50'
  },
  statusTextDisconnected: {
    color: '#F44336'
  },
  helpButton: {
    backgroundColor: '#2E2E2E',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 5,
    borderWidth: 1,
    borderColor: '#3A3A3A',
    height: 44,
    width: 44,
    justifyContent: 'center',
    alignItems: 'center'
  },
  buttonsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20
  },
  connectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2E2E2E',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 18,
    flex: 1,
    marginRight: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 5,
    borderWidth: 1,
    borderColor: '#3A3A3A',
    height: 56
  },
  connectButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'Inter, sans-serif',
    letterSpacing: 0.3,
    marginLeft: 10
  },
  connectButtonSubText: {
    color: '#FFCF00',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'Inter, sans-serif'
  },
  dashboardContainer: {
    width: '100%'
  },
  obdPanel: {
    backgroundColor: '#2E2E2E',
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 10
  },
  panelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#444'
  },
  panelTitle: {
    color: '#FFCF00',
    fontSize: 16,
    fontWeight: 'bold',
    marginLeft: 12,
    fontFamily: 'Inter, sans-serif'
  },
  mainGaugesRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 20
  },
  gaugeItem: {
    alignItems: 'center'
  },
  gaugeValue: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: 'bold',
    marginTop: 8
  },
  gaugeValueNA: {
    color: '#666666',
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
    fontStyle: 'italic'
  },
  gaugeUnit: {
    color: '#999',
    fontSize: 12,
    marginTop: 4
  },
  dataGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between'
  },
  dataCard: {
    width: '48%',
    backgroundColor: '#3A3A3A',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    alignItems: 'center',
    minHeight: 110
  },
  dataCardLabel: {
    color: '#999',
    fontSize: 11,
    marginTop: 8,
    textAlign: 'center'
  },
  dataCardValue: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 4
  },
  dataCardValueNA: {
    color: '#666666',
    fontSize: 16,
    fontWeight: '500',
    marginTop: 8,
    fontStyle: 'italic'
  },
  dtcHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16
  },
  dtcCount: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold'
  },
  dtcItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3A3A3A',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12
  },
  dtcSeverity: {
    width: 6,
    height: '100%',
    minHeight: 50,
    borderRadius: 3,
    marginRight: 12
  },
  dtcInfo: {
    flex: 1
  },
  dtcCode: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold'
  },
  dtcDescription: {
    color: '#999',
    fontSize: 12,
    marginTop: 4
  },
  noDtcContainer: {
    alignItems: 'center',
    paddingVertical: 40
  },
  noDtcText: {
    color: '#999',
    fontSize: 16,
    marginTop: 12
  },
  readDtcBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#3A3A3A',
    borderRadius: 12,
    paddingVertical: 12,
    marginTop: 16
  },
  readDtcText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 8
  },
  consumptionGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between'
  },
  consumptionCard: {
    width: '48%',
    backgroundColor: '#3A3A3A',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    minHeight: 150
  },
  consumptionValue: {
    color: '#FFCF00',
    fontSize: 32,
    fontWeight: 'bold',
    marginTop: 12
  },
  consumptionValueNA: {
    color: '#666666',
    fontSize: 20,
    fontWeight: '500',
    marginTop: 20,
    fontStyle: 'italic'
  },
  consumptionUnit: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600'
  },
  consumptionLabel: {
    color: '#999',
    fontSize: 12,
    marginTop: 4
  },
  fuelTrimsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20
  },
  fuelTrimItem: {
    width: '48%',
    backgroundColor: '#3A3A3A',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center'
  },
  fuelTrimLabel: {
    color: '#999',
    fontSize: 12
  },
  fuelTrimValue: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 4
  },
  fuelTrimValueNA: {
    color: '#666666',
    fontSize: 16,
    fontWeight: '500',
    marginTop: 8,
    fontStyle: 'italic'
  },
  actionButtonsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%'
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2E2E2E',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
    width: '48%'
  },
  actionButtonDanger: {
    backgroundColor: '#F44336'
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 8
  },
  actionButtonTextWhite: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 8
  },
  connectionSection: {
    width: '100%'
  },
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 40
  },
  loadingText: {
    color: '#666',
    fontSize: 16,
    marginTop: 16
  },
  deviceListContainer: {
    width: '100%'
  },
  deviceListTitle: {
    color: '#333',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16
  },
  deviceItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12
  },
  deviceInfo: {
    flex: 1,
    marginLeft: 12
  },
  deviceName: {
    color: '#333',
    fontSize: 16,
    fontWeight: '600'
  },
  deviceAddress: {
    color: '#666',
    fontSize: 12,
    marginTop: 4
  },
  bottomSpacer: {
    height: 100
  },
  modalContainer: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end'
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    maxHeight: '85%'
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24
  },
  modalTitle: {
    color: '#333',
    fontSize: 20,
    fontWeight: 'bold'
  },
  closeButton: {
    padding: 4
  },
  modalScroll: {
    maxHeight: '80%'
  },
  stepItem: {
    flexDirection: 'row',
    marginBottom: 24
  },
  stepNumber: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FFCF00',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16
  },
  stepNumberText: {
    color: '#000',
    fontSize: 18,
    fontWeight: 'bold'
  },
  stepText: {
    flex: 1,
    color: '#333',
    fontSize: 16,
    lineHeight: 24
  }
});

export default OBDScreen;
