import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, ScrollView, Platform, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { useFocusEffect } from '@react-navigation/native';
import API_BASE_URL from '../api';
import BottomNav from '../components/NavBar/BottomNav';
import Header from '../components/Header/Header';
import WelcomeBanner from '../components/Home/WelcomeBanner';
import DashboardGrid from '../components/Home/DashboardGrid';
import AMPAlertModal from '../components/Common/AMPAlertModal';

const HomeScreen = ({ navigation, route }) => {
  const loggedUser = route.params?.user;

  const [status, setStatus] = useState({
    user_name: loggedUser?.full_name || 'Usuário',
    recommendation: 'Carregando informações...',
    vehicle: null,
    is_premium: loggedUser?.is_premium || false
  });

  const [profileForm, setProfileForm] = useState({
    full_name: loggedUser?.full_name || '',
    email: loggedUser?.email || '',
    phone: loggedUser?.phone || '',
  });
  const [avatarUri, setAvatarUri] = useState(loggedUser?.avatar_url || null);
  const [savingProfile, setSavingProfile] = useState(false);
  
  // Modal state
  const [modalVisible, setModalVisible] = useState(false);
  const [modalData, setModalData] = useState({
    type: 'info',
    title: '',
    message: '',
  });

  // ----- Estado do Header (notificações + plano/veículos) -----
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [planType, setPlanType] = useState(loggedUser?.plan_type || null);
  const [vehicle, setVehicle] = useState(null); // Single vehicle

  const hasCriticalNotif = notifications.some((n) => !n.read && n.priority && String(n.priority).toLowerCase() === 'critical');

  useEffect(() => {
  console.log('loggedUser mudou:', loggedUser);
  if (loggedUser?.id) {
    fetchUserStatus();
    fetchNotifications();
  }
  }, [route.params?.user, loggedUser?.id]);

  const fetchUserStatus = async () => {
    if (!loggedUser?.id) return;
    try {
      const userId = loggedUser.id;
      const response = await axios.get(`${API_BASE_URL}/user/status/${userId}`);

      let isPremium = loggedUser?.is_premium || false;
      try {
        const userResponse = await axios.get(`${API_BASE_URL}/user/${userId}`);
        isPremium = userResponse.data.is_premium;
        setPlanType(userResponse.data.plan_type || null);
      } catch (err) {
        console.error('Error fetching user details:', err);
      }

      const vehicleData = Array.isArray(response.data?.vehicles)
        ? response.data.vehicles[0]
        : response.data?.vehicle || null;
      setVehicle(vehicleData);

      setStatus((prev) => ({
        ...prev,
        ...response.data,
        user_name: response.data?.user_name || loggedUser?.full_name || 'Usuário',
        is_premium: isPremium
      }));
    } catch (error) {
      console.error('Error fetching status:', error);
      setStatus({
        user_name: loggedUser?.full_name || 'Usuário',
        recommendation: 'Nenhuma recomendação no momento.',
        vehicle: null,
        is_premium: loggedUser?.is_premium || false
      });
    }
  };

  const fetchNotifications = async (forceRefresh = false) => {
    try {
      const userId = loggedUser?.id || 1;
      const url = forceRefresh
        ? `${API_BASE_URL}/user/notifications/${userId}?refresh=1`
        : `${API_BASE_URL}/user/notifications/${userId}`;
      const res = await axios.get(url, { timeout: 30000 });

      const data = Array.isArray(res.data?.notifications) ? res.data.notifications : [];
      setNotifications(data);

      const backendCount = typeof res.data?.unread_count === 'number' ? res.data.unread_count : null;
      if (backendCount !== null && !Number.isNaN(backendCount)) {
        setUnreadCount(backendCount);
      } else {
        setUnreadCount(data.filter((n) => !n.read).length);
      }
    } catch (error) {
      console.error('Error fetching notifications:', error);
      if (!forceRefresh && loggedUser?.id) {
        try {
          const fallbackRes = await axios.get(`${API_BASE_URL}/user/notifications/${loggedUser.id}?refresh=1`, { timeout: 15000 });
          const fallbackData = Array.isArray(fallbackRes.data?.notifications) ? fallbackRes.data.notifications : [];
          setNotifications(fallbackData);
          const count = typeof fallbackRes.data?.unread_count === 'number'
            ? fallbackRes.data.unread_count
            : fallbackData.filter((n) => !n.read).length;
          setUnreadCount(count);
        } catch (e2) {
          console.error('Fallback fetch também falhou:', e2);
        }
      }
    }
  };

  useFocusEffect(
    useCallback(() => {
      if (!loggedUser?.id) {
        return undefined;
      }

      fetchUserStatus();
      fetchNotifications();

      return undefined;
    }, [loggedUser?.id])
  );

  const handlePremiumButton = () => {
    if (!status.is_premium) {
      navigation.navigate('VehicleCompatibility', { user: loggedUser, vehicle: status.vehicle });
    }
  };

  const handleProfileFieldChange = (field, value) => {
    setProfileForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleChangePhoto = async () => {
    try {
      // Request permission first
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permissão negada', 'Precisamos de acesso à galeria para trocar a foto.');
        return;
      }

      // Launch image picker
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [4, 4],
        quality: 0.7,
        base64: true,
      });

      if (!result.canceled) {
        const selectedImage = result.assets[0];
        // Set as data URI (base64)
        const base64Uri = `data:image/jpeg;base64,${selectedImage.base64}`;
        setAvatarUri(base64Uri);
      }
    } catch (error) {
      console.error('Error picking image:', error);
      Alert.alert('Erro', 'Não foi possível selecionar a foto.');
    }
  };

  const handleSaveProfile = async () => {
    try {
      setSavingProfile(true);
      const userId = loggedUser?.id || 1;
      const updateData = {
        full_name: profileForm.full_name,
        email: profileForm.email,
        phone: profileForm.phone,
      };
      
      // Include avatar if it's been changed
      if (avatarUri) {
        updateData.avatar = avatarUri;
      }

      await axios.put(`${API_BASE_URL}/user/${userId}`, updateData);
      setStatus((prev) => ({ ...prev, user_name: profileForm.full_name }));
      
      setModalData({
        type: 'success',
        title: 'Sucesso!',
        message: 'Suas informações foram salvas com sucesso.',
      });
      setModalVisible(true);
    } catch (error) {
      console.error('Error saving profile:', error);
      setModalData({
        type: 'error',
        title: 'Erro',
        message: 'Não foi possível salvar suas informações agora.',
      });
      setModalVisible(true);
    } finally {
      setSavingProfile(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Sair da conta', 'Tem certeza que deseja sair?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Sair',
        style: 'destructive',
        onPress: () => {
          navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
        }
      }
    ]);
  };

  const markAllAsRead = async () => {
    if (!loggedUser?.id) return;
    try {
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
      await axios.patch(
        `${API_BASE_URL}/user/notifications/${loggedUser.id}/read-all`,
        {},
        { timeout: 15000 }
      ).catch((e) => console.warn('mark-all-read endpoint error (segue com UI atualizada):', e?.message || e));
    } catch (e) {
      console.error('markAllAsRead failed:', e);
    }
  };

  const handleAddVehicle = () => {
    navigation.navigate('VehicleEditScreen', { user: loggedUser });
  };

  return (
    <View style={styles.container}>
      {/*
        O Header já renderiza o NotificationsModal e o ProfileModal
        internamente, então não é preciso duplicá-los aqui.
      */}
      <Header
        avatarUri={avatarUri}
        notifications={notifications}
        notificationCount={unreadCount}
        onMarkAllAsRead={markAllAsRead}
        profileForm={profileForm}
        onChangeField={handleProfileFieldChange}
        onChangePhoto={handleChangePhoto}
        onSaveProfile={handleSaveProfile}
        savingProfile={savingProfile}
        onLogout={handleLogout}
        isPremium={status.is_premium}
        planType={planType}
        vehicle={vehicle}
        navigation={navigation}
        loggedUser={loggedUser}
      />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={true}
        scrollEnabled={true}
      >
        <WelcomeBanner userName={status.user_name} recommendation={status.recommendation} />

        <DashboardGrid
          onPressOBD={() =>
            !status.is_premium
              ? navigation.navigate('VehicleCompatibility', { user: loggedUser, vehicle: status.vehicle })
              : navigation.navigate('OBD', { user: loggedUser })
          }
          onPressTravelPlanning={() => navigation.navigate('TravelPlanning', { user: loggedUser })}
          onPressVehicleEditScreen={() => navigation.navigate('VehicleEditScreen', { user: loggedUser })}
          onPressMaintenanceTips={
            status.is_premium
              ? () => navigation.navigate('MaintenanceTips', { user: loggedUser })
              : handlePremiumButton
          }
          OBDHistory={
            status.is_premium
              ? () => navigation.navigate('OBDHistory', { user: loggedUser })
              : handlePremiumButton
          }
          onPressTripHistory={() => navigation.navigate('TripHistory', { user: loggedUser })}
          onPressCompatibility={() =>
            navigation.navigate('VehicleCompatibility', { user: loggedUser, vehicle: status.vehicle })
          }
        />

        <View style={styles.emptySpace} />
      </ScrollView>

      <BottomNav navigation={navigation} user={loggedUser} activeScreen="Home" />
      <AMPAlertModal
        visible={modalVisible}
        type={modalData.type}
        title={modalData.title}
        message={modalData.message}
        onClose={() => setModalVisible(false)}
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
  scrollView: {
    flex: 1,
    ...Platform.select({
      web: {
        overflowY: 'scroll'
      }
    })
  },
  content: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingBottom: 100,
    alignItems: 'center'
  },
  emptySpace: {
    height: 100
  }
});

export default HomeScreen;
