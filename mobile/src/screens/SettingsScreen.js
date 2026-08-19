import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, Platform, Alert } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import axios from 'axios';
import { useFocusEffect } from '@react-navigation/native';
import API_BASE_URL from '../api';
import BottomNav from '../components/NavBar/BottomNav';
import Header from '../components/Header/Header';
import SectionCard from '../components/Settings/SectionCard';
import MenuItem from '../components/Settings/MenuItem';
import DeleteAccountModal from '../components/Settings/DeleteAccountModal';
import NotificationService from '../utils/NotificationService';
import PrimaryButton from '../components/Common/PrimaryButton';

const DEFAULT_PREFS = {
    notifications_enabled: true,
    notif_maintenance: true,
    notif_obd: true,
    notif_fuel: true,
    notif_tips: true,
    notif_milestones: true,
    notif_system: true,
    premium_ai_insights: true,
    premium_predictive: true,
    premium_driving_analysis: true,
    premium_seasonal: true,
    premium_smart_frequency: true,
};

const SettingsScreen = ({ navigation, route }) => {
    const loggedUser = route.params?.user;

    const [notificationsDisabled, setNotificationsDisabled] = useState(false);
    const [biometryEnabled, setBiometryEnabled] = useState(true);
    const [locationEnabled, setLocationEnabled] = useState(true);
    const [deleteModalVisible, setDeleteModalVisible] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const [prefs, setPrefs] = useState(DEFAULT_PREFS);
    const [savingPrefs, setSavingPrefs] = useState(false);
    const [loadingPrefs, setLoadingPrefs] = useState(false);
    const [regeneratingAi, setRegeneratingAi] = useState(false);

    const [notifications, setNotifications] = useState([]);
    const [notificationCount, setNotificationCount] = useState(0);
    const [avatarUri, setAvatarUri] = useState(loggedUser?.avatar_url || null);
    const [profileForm, setProfileForm] = useState({
        full_name: loggedUser?.full_name || loggedUser?.name || '',
        email: loggedUser?.email || '',
        phone: loggedUser?.phone || ''
    });
    const [savingProfile, setSavingProfile] = useState(false);
    const [isPremium, setIsPremium] = useState(!!loggedUser?.is_premium);
    const [planType, setPlanType] = useState(loggedUser?.plan_type || null);
    const [vehicle, setVehicle] = useState(null);
    const [unsubscribeNotif, setUnsubscribeNotif] = useState(null);

    useEffect(() => {
        if (loggedUser?.id) {
            NotificationService.bootstrap(loggedUser.id, !!loggedUser?.is_premium).catch(() => {});
            const unsub = NotificationService.subscribe((evt) => {
                setNotificationCount(evt.unreadCount || 0);
            });
            setUnsubscribeNotif(() => unsub);
            loadEverything();
        }
        return () => {
            if (unsubscribeNotif) {
                try { unsubscribeNotif(); } catch {}
            }
        };
    }, [loggedUser?.id]);

    useEffect(() => {
        setNotificationsDisabled(prefs.notifications_enabled === false);
    }, [prefs.notifications_enabled]);

    const loadEverything = async () => {
        await Promise.all([
            fetchNotifications(true),
            fetchUserData(),
            fetchNotificationPreferences(true),
        ]);
    };

    const fetchUserData = async () => {
        try {
            const userId = loggedUser?.id || 1;
            const statusRes = await axios.get(`${API_BASE_URL}/user/status/${userId}`);
            if (statusRes.data?.user) {
                const u = statusRes.data.user;
                setProfileForm({
                    full_name: u.full_name || u.name || '',
                    email: u.email || '',
                    phone: u.phone || ''
                });
                setAvatarUri(u.avatar_url || null);
                setIsPremium(!!u.is_premium);
                setPlanType(u.plan_type || null);
            }
            const vehicleData = Array.isArray(statusRes.data?.vehicles)
                ? statusRes.data.vehicles[0]
                : statusRes.data?.vehicle || null;
            setVehicle(vehicleData);
        } catch (error) {
            console.error('Erro ao buscar dados do usuário:', error);
        }
    };

    const fetchNotificationPreferences = async (useService = false) => {
        if (!loggedUser?.id) return;
        setLoadingPrefs(true);
        try {
            let data;
            if (useService && NotificationService.userId === loggedUser.id) {
                data = await NotificationService.fetchPreferences();
            } else {
                const res = await axios.get(`${API_BASE_URL}/user/${loggedUser.id}/notification-preferences`, { timeout: 15000 });
                data = res.data?.preferences || null;
            }
            if (data) {
                setPrefs((prev) => ({ ...prev, ...data }));
            }
        } catch (error) {
            console.error('Erro ao buscar preferências:', error);
        } finally {
            setLoadingPrefs(false);
        }
    };

    const saveNotificationPreferences = async (patch = {}) => {
        if (!loggedUser?.id) return;
        const newPrefs = { ...prefs, ...patch };
        setPrefs(newPrefs);
        setSavingPrefs(true);
        try {
            await NotificationService.savePreferences(newPrefs);
        } catch (error) {
            console.error('Erro ao salvar preferências:', error);
            Alert.alert('Erro', 'Não foi possível salvar preferências agora. Tente novamente.');
        } finally {
            setSavingPrefs(false);
        }
    };

    const toggleNotificationsEnabled = async (val) => {
        await saveNotificationPreferences({ notifications_enabled: val });
    };

    const toggleNotif = async (key) => {
        if (!prefs.notifications_enabled) return;
        await saveNotificationPreferences({ [key]: !prefs[key] });
    };

    const handleRegenerateAI = async () => {
        if (!isPremium) return;
        setRegeneratingAi(true);
        try {
            await NotificationService.regeneratePremiumInsights();
            Alert.alert('Sucesso', 'Novos insights Premium gerados com sucesso!');
        } catch (error) {
            console.error('Erro ao regenerar IA:', error);
            Alert.alert('Erro', 'Não foi possível gerar novos insights agora.');
        } finally {
            setRegeneratingAi(false);
        }
    };

    const fetchNotifications = async (skipServiceRefresh = false) => {
        try {
            const userId = loggedUser?.id || 1;
            const res = await axios.get(`${API_BASE_URL}/user/notifications/${userId}`);
            const data = Array.isArray(res.data?.notifications) ? res.data.notifications : [];
            setNotifications(data);
            const backendCount = typeof res.data?.unread_count === 'number' ? res.data.unread_count : null;
            const count = backendCount !== null ? backendCount : data.filter((n) => !n.read).length;
            const effective = prefs.notifications_enabled === false ? 0 : count;
            setNotificationCount(effective);
        } catch (error) {
            console.error('Erro ao buscar notificações:', error);
        }
    };

    useFocusEffect(
        useCallback(() => {
            if (!loggedUser?.id) {
                return undefined;
            }

            loadEverything();

            return undefined;
        }, [loggedUser?.id])
    );

    const handleMarkAllAsRead = async () => {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        setNotificationCount(0);
        try {
            await NotificationService.markAllAsRead();
        } catch (error) {
            console.error('Erro ao marcar notificações como lidas:', error);
        }
    };

    const handleChangeField = (field, value) => {
        setProfileForm((prev) => ({ ...prev, [field]: value }));
    };

    const handleChangePhoto = async () => {
        Alert.alert('Em breve', 'Seleção de foto ainda não implementada.');
    };

    const handleSaveProfile = async () => {
        try {
            setSavingProfile(true);
            const userId = loggedUser?.id || 1;
            await axios.patch(`${API_BASE_URL}/user/${userId}`, profileForm);
            Alert.alert('Sucesso', 'Perfil atualizado com sucesso!');
        } catch (error) {
            console.error('Erro ao salvar perfil:', error);
            Alert.alert('Erro', 'Não foi possível salvar o perfil. Tente novamente.');
        } finally {
            setSavingProfile(false);
        }
    };

    const handleAddVehicle = () => {
        navigation.navigate('AddVehicle', { user: loggedUser });
    };

    const handleLogout = () => {
        Alert.alert('Sair', 'Deseja realmente sair da conta?', [
            { text: 'Cancelar', style: 'cancel' },
            {
                text: 'Sair',
                style: 'destructive',
                onPress: () => {
                    try { NotificationService.reset(); } catch {}
                    navigation.reset({
                        index: 0,
                        routes: [{ name: 'Login' }],
                    });
                }
            }
        ]);
    };

    const openDeleteModal = () => setDeleteModalVisible(true);

    const cancelDelete = () => {
        if (isDeleting) return;
        setDeleteModalVisible(false);
    };

    const confirmDeleteAccount = async () => {
        if (!loggedUser?.id) {
            Alert.alert('Erro', 'Usuário não identificado. Faça login novamente.');
            return;
        }

        try {
            setIsDeleting(true);
            await axios.delete(`${API_BASE_URL}/user/${loggedUser.id}`);

            setIsDeleting(false);
            setDeleteModalVisible(false);
            try { NotificationService.reset(); } catch {}

            Alert.alert('Conta excluída', 'Sua conta e todos os dados foram removidos com sucesso.');

            navigation.reset({
                index: 0,
                routes: [{ name: 'Login' }],
            });
        } catch (error) {
            console.error('Erro ao excluir conta:', error);
            console.error('Detalhes do erro:', error.response?.data || error.message);
            setIsDeleting(false);
            Alert.alert('Erro', 'Não foi possível excluir sua conta agora. Tente novamente mais tarde.');
        }
    };

    return (
        <View style={styles.container}>
            <Header
                avatarUri={avatarUri}
                notifications={notifications}
                notificationCount={notificationCount}
                notificationsEnabled={prefs.notifications_enabled !== false}
                onMarkAllAsRead={handleMarkAllAsRead}
                profileForm={profileForm}
                onChangeField={handleChangeField}
                onChangePhoto={handleChangePhoto}
                onSaveProfile={handleSaveProfile}
                savingProfile={savingProfile}
                onLogout={handleLogout}
                isPremium={isPremium}
                planType={planType}
                vehicle={vehicle}
                navigation={navigation}
                loggedUser={loggedUser}
            />

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={true}
            >
                <Text style={styles.screenTitle}>CONFIGURAÇÕES</Text>

                <SectionCard title="Notificações">
                    <MenuItem
                        icon={<MaterialCommunityIcons name="bell-off-outline" size={20} color="#2D2D2D" />}
                        label="Desativar Todas as Notificações"
                        switchValue={notificationsDisabled}
                        onSwitchChange={(val) => toggleNotificationsEnabled(!val)}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="wrench-outline" size={20} color="#2D2D2D" />}
                        label="Lembretes de Manutenção"
                        switchValue={prefs.notif_maintenance}
                        onSwitchChange={() => toggleNotif('notif_maintenance')}
                        disabled={notificationsDisabled || savingPrefs}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="car-connected" size={20} color="#2D2D2D" />}
                        label="Alertas OBD-II"
                        switchValue={prefs.notif_obd}
                        onSwitchChange={() => toggleNotif('notif_obd')}
                        disabled={notificationsDisabled || savingPrefs}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="gas-station-outline" size={20} color="#2D2D2D" />}
                        label="Dicas de Combustível"
                        switchValue={prefs.notif_fuel}
                        onSwitchChange={() => toggleNotif('notif_fuel')}
                        disabled={notificationsDisabled || savingPrefs}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="lightbulb-on-outline" size={20} color="#2D2D2D" />}
                        label="Dicas e Sugestões"
                        switchValue={prefs.notif_tips}
                        onSwitchChange={() => toggleNotif('notif_tips')}
                        disabled={notificationsDisabled || savingPrefs}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="trophy-outline" size={20} color="#2D2D2D" />}
                        label="Marco e Conquistas"
                        switchValue={prefs.notif_milestones}
                        onSwitchChange={() => toggleNotif('notif_milestones')}
                        disabled={notificationsDisabled || savingPrefs}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="car-cog" size={20} color="#2D2D2D" />}
                        label="Lembretes Programáveis"
                        disabled={notificationsDisabled}
                        onPress={() => navigation.navigate('Reminders', { user: loggedUser })}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="cash-multiple" size={20} color="#2D2D2D" />}
                        label="Frequência dos Lembretes"
                        disabled={notificationsDisabled}
                        onPress={() => navigation.navigate('ReminderFrequency', { user: loggedUser })}
                    />
                </SectionCard>

                {isPremium && (
                    <SectionCard title="Notificações Premium IA ✨" headerIcon="star">
                        <MenuItem
                            icon={<MaterialCommunityIcons name="robot-outline" size={20} color="#B8860B" />}
                            label="Insights Gerados por IA"
                            switchValue={prefs.premium_ai_insights}
                            onSwitchChange={() => toggleNotif('premium_ai_insights')}
                            disabled={notificationsDisabled || savingPrefs}
                        />
                        <MenuItem
                            icon={<MaterialCommunityIcons name="crystal-ball" size={20} color="#B8860B" />}
                            label="Alertas Preditivos"
                            switchValue={prefs.premium_predictive}
                            onSwitchChange={() => toggleNotif('premium_predictive')}
                            disabled={notificationsDisabled || savingPrefs}
                        />
                        <MenuItem
                            icon={<MaterialCommunityIcons name="steering" size={20} color="#B8860B" />}
                            label="Análise de Direção e Economia"
                            switchValue={prefs.premium_driving_analysis}
                            onSwitchChange={() => toggleNotif('premium_driving_analysis')}
                            disabled={notificationsDisabled || savingPrefs}
                        />
                        <MenuItem
                            icon={<MaterialCommunityIcons name="weather-sunny" size={20} color="#B8860B" />}
                            label="Recomendações Sazonais"
                            switchValue={prefs.premium_seasonal}
                            onSwitchChange={() => toggleNotif('premium_seasonal')}
                            disabled={notificationsDisabled || savingPrefs}
                        />
                        <MenuItem
                            icon={<MaterialCommunityIcons name="timer-cog-outline" size={20} color="#B8860B" />}
                            label="Frequência Inteligente (2x mais rápida)"
                            switchValue={prefs.premium_smart_frequency}
                            onSwitchChange={() => toggleNotif('premium_smart_frequency')}
                            disabled={notificationsDisabled || savingPrefs}
                        />

                        <View style={{ paddingHorizontal: 20, paddingVertical: 15 }}>
                            <PrimaryButton
                                label="Gerar Novos Insights IA Agora"
                                onPress={handleRegenerateAI}
                                loading={regeneratingAi}
                                disabled={notificationsDisabled || loadingPrefs}
                                icon={<MaterialCommunityIcons name="auto-fix" size={18} color="#000" style={{ marginRight: 6 }} />}
                            />
                        </View>
                    </SectionCard>
                )}

                <SectionCard title="Preferências">
                    <MenuItem
                        icon={<MaterialCommunityIcons name="fingerprint" size={20} color="#2D2D2D" />}
                        label="Ativar/Desativar Biometria"
                        switchValue={biometryEnabled}
                        onSwitchChange={setBiometryEnabled}
                    />
                </SectionCard>

                <SectionCard title="Ajuda e Suporte" headerIcon="info">
                    <MenuItem
                        icon={<MaterialCommunityIcons name="help-circle-outline" size={20} color="#2D2D2D" />}
                        label="FAQ"
                        onPress={() => navigation.navigate('FAQ', { user: loggedUser })}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="translate" size={20} color="#2D2D2D" />}
                        label="Idioma"
                        onPress={() => navigation.navigate('LanguageSelection', { user: loggedUser })}
                    />
                </SectionCard>

                <SectionCard title="Privacidade e Segurança" headerIcon="lock">
                    <MenuItem
                        icon={<MaterialCommunityIcons name="map-marker-outline" size={20} color="#2D2D2D" />}
                        label="Permitir Localização"
                        switchValue={locationEnabled}
                        onSwitchChange={setLocationEnabled}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="file-document-outline" size={20} color="#2D2D2D" />}
                        label="Política de Termos e Condições"
                        onPress={() => navigation.navigate('TermsOfService', { user: loggedUser })}
                    />
                    <MenuItem
                        icon={<MaterialCommunityIcons name="trash-can-outline" size={20} color="#FF4444" />}
                        label="Apagar Conta/Apagar Dados"
                        danger
                        onPress={openDeleteModal}
                    />
                </SectionCard>

                <View style={styles.footerSpace} />
            </ScrollView>

            <BottomNav navigation={navigation} user={loggedUser} activeScreen="Config" />

            <DeleteAccountModal
                visible={deleteModalVisible}
                isDeleting={isDeleting}
                onCancel={cancelDelete}
                onConfirm={confirmDeleteAccount}
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
        overflow: 'hidden',
      },
      default: {
        flex: 1,
      }
    })
  },
  scrollView: {
    flex: 1,
    ...Platform.select({
      web: {
        overflowY: 'scroll',
      }
    })
  },
  scrollContent: {
    paddingHorizontal: 15,
    paddingTop: 10,
    paddingBottom: 100,
  },
  screenTitle: {
    fontSize: 22,
    fontWeight: '800',
    textAlign: 'center',
    color: '#000000',
    marginVertical: 15,
  },
  footerSpace: {
    height: 20,
  },
});

export default SettingsScreen;
