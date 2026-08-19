import React, { useState } from 'react';
import { View, Image, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons, FontAwesome5 } from '@expo/vector-icons';
import NotificationsModal from './NotificationsModal';
import ProfileModal from './ProfileModal';

/**
 * Header fixo padrão do app.
 *
 * Por padrão, tocar no sino abre o NotificationsModal e tocar no avatar
 * abre o ProfileModal — ambos renderizados aqui dentro. Se quiser navegar
 * para uma tela em vez de abrir o modal, passe onLeftIconPress/onRightIconPress.
 */
const hasValidCount = (count) => {
  if (count === null || count === undefined || count === '') return false;
  const n = Number(count);
  return Number.isFinite(n) && n > 0;
};

const Header = ({
  logoSource = require('../../assets/logo.png'),
  onLeftIconPress,
  onRightIconPress,
  leftIcon,
  rightIcon,
  notifications,
  notificationCount = 0,
  onMarkAllAsRead,
  avatarUri,
  profileForm = { full_name: '', email: '', phone: '' },
  onChangeField,
  onChangePhoto,
  onSaveProfile,
  savingProfile,
  onLogout,
  isPremium = false,
  planType,
  vehicle = null, // Single vehicle
  showIcons = true,
  style,
  navigation,
  loggedUser,
  hasCritical = false
}) => {
  const [notificationsVisible, setNotificationsVisible] = useState(false);
  const [profileVisible, setProfileVisible] = useState(false);
  const safeCount = hasValidCount(notificationCount) ? Math.min(Number(notificationCount), 99) : 0;

  const handleLeftIconPress = () => {
    if (onLeftIconPress) {
      onLeftIconPress();
      return;
    }
    setNotificationsVisible(true);
  };

  const handleRightIconPress = () => {
    if (onRightIconPress) {
      onRightIconPress();
      return;
    }
    setProfileVisible(true);
  };

  const renderBellIcon = () => {
    if (leftIcon) return leftIcon;
    if (safeCount <= 0) {
      return <Ionicons name="notifications-outline" size={26} color="#2C2C2C" />;
    }
    if (hasCritical) {
      return <Ionicons name="notifications" size={26} color="#F44336" />;
    }
    return <Ionicons name="notifications" size={26} color="#2C2C2C" />;
  };

  return (
    <View style={[styles.header, showIcons ? styles.headerWithIcons : styles.headerWithoutIcons, style]}>
      <NotificationsModal
        visible={notificationsVisible}
        onClose={() => setNotificationsVisible(false)}
        notifications={notifications}
        unreadCount={safeCount}
        onMarkAllAsRead={onMarkAllAsRead}
        isPremium={isPremium}
      />
      <ProfileModal
        visible={profileVisible}
        onClose={() => setProfileVisible(false)}
        profileForm={profileForm}
        onChangeField={onChangeField}
        avatarUri={avatarUri}
        onChangePhoto={onChangePhoto}
        onSave={onSaveProfile}
        saving={savingProfile}
        onLogout={onLogout}
        isPremium={isPremium}
        planType={planType}
        vehicle={vehicle}
        navigation={navigation}
        loggedUser={loggedUser}
      />

      <Image source={logoSource} style={styles.logo} resizeMode="contain" />

      {showIcons && (
        <View style={styles.headerIcons}>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={handleLeftIconPress}
            activeOpacity={0.7}
            hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}
          >
            {renderBellIcon()}
            {safeCount > 0 && (
              <View style={[
                styles.badge,
                hasCritical && styles.badgeCritical,
                safeCount > 9 && styles.badgeWide
              ]}>
                <Text style={styles.badgeText}>
                  {safeCount > 99 ? '99+' : safeCount > 9 ? '9+' : safeCount}
                </Text>
              </View>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.iconButton}
            onPress={handleRightIconPress}
            activeOpacity={0.7}
            hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}
          >
            {rightIcon || (
              <View style={styles.avatarPlaceholder}>
                {avatarUri ? (
                  <Image source={{ uri: avatarUri }} style={styles.avatarImage} />
                ) : (
                  <FontAwesome5 name="user-alt" size={16} color="#FFCF00" />
                )}
              </View>
            )}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 10,
    height: 70,
    backgroundColor: '#fff',
    overflow: 'visible'
  },
  headerWithIcons: {
    justifyContent: 'space-between'
  },
  headerWithoutIcons: {
    justifyContent: 'center'
  },
  logo: {
  width: 120,
  height: 60,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    overflow: 'visible'
  },
  iconButton: {
    marginLeft: 18,
    position: 'relative',
    overflow: 'visible',
    padding: 4
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -8,
    backgroundColor: '#F44336',
    borderWidth: 1.5,
    borderColor: '#FFFFFF',
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 999,
    elevation: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.3,
    shadowRadius: 2
  },
  badgeWide: {
    minWidth: 22,
    paddingHorizontal: 5
  },
  badgeCritical: {
    backgroundColor: '#D32F2F'
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    lineHeight: 12,
    fontWeight: '900',
    fontFamily: 'Inter, sans-serif'
  },
  avatarPlaceholder: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#2C2C2C',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden'
  },
  avatarImage: {
    width: 34,
    height: 34,
    borderRadius: 17
  }
});

export default React.memo(Header);