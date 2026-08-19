import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Modal,
  Pressable
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';

const PRIORITY_BG = {
  critical: '#FFEBEE',
  high: '#FFF3E0',
  medium: '#FFFDE7',
  low: '#F5F5F5'
};

const PRIORITY_ACCENT = {
  critical: '#D32F2F',
  high: '#F57C00',
  medium: '#FBC02D',
  low: '#757575'
};

const PRIORITY_LABEL = {
  critical: 'Crítico',
  high: 'Alta',
  medium: 'Média',
  low: 'Baixa'
};

const TYPE_ICONS = {
  maintenance: { family: 'MaterialCommunityIcons', name: 'wrench', color: '#FF9800' },
  obd: { family: 'MaterialCommunityIcons', name: 'car-connected', color: '#F44336' },
  tip: { family: 'MaterialCommunityIcons', name: 'lightbulb-on', color: '#FFC107' },
  milestone: { family: 'MaterialCommunityIcons', name: 'trophy', color: '#9C27B0' },
  premium: { family: 'MaterialCommunityIcons', name: 'star-four-points', color: '#FFD700' },
  fuel: { family: 'MaterialCommunityIcons', name: 'gas-station', color: '#4CAF50' },
  system: { family: 'Ionicons', name: 'information-circle', color: '#2196F3' }
};

const getTypeIcon = (item) => {
  const config = TYPE_ICONS[item?.type] || TYPE_ICONS.system;
  if (config.family === 'MaterialCommunityIcons') {
    return <MaterialCommunityIcons name={config.name} size={20} color={config.color} />;
  }
  return <Ionicons name={config.name} size={20} color={config.color} />;
};

const NotificationsModal = ({
  visible,
  onClose,
  notifications,
  unreadCount,
  onMarkAllAsRead,
  isPremium = false
}) => {
  const effectiveUnreadCount =
    typeof unreadCount === 'number' && !Number.isNaN(unreadCount)
      ? unreadCount
      : (Array.isArray(notifications) ? notifications.filter((n) => !n.read).length : 0);

  const list = Array.isArray(notifications) && notifications.length > 0
    ? [...notifications].sort((a, b) => {
        const weight = { critical: 4, high: 3, medium: 2, low: 1 };
        const wA = a.read ? 0 : (weight[a.priority] || 2);
        const wB = b.read ? 0 : (weight[b.priority] || 2);
        if (wA !== wB) return wB - wA;
        const idA = Number(a.id) || 0;
        const idB = Number(b.id) || 0;
        return idB - idA;
      })
    : [];

  const renderTag = (item, key, label, color, bg) => (
    <View key={key} style={[styles.tag, { backgroundColor: bg }]}>
      <Text style={[styles.tagText, { color }]}>{label}</Text>
    </View>
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable
          style={styles.notificationModalCard}
          onPress={() => {}}
        >
          <View style={styles.modalHandle} />

          <View style={styles.modalHeaderRow}>
            <View style={styles.modalTitleRow}>
              <Ionicons name="notifications" size={22} color="#2C2C2C" />
              <Text style={styles.modalTitle}>Notificações</Text>
              {effectiveUnreadCount > 0 && (
                <View style={styles.headerBadge}>
                  <Text style={styles.headerBadgeText}>{effectiveUnreadCount}</Text>
                </View>
              )}
            </View>

            <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}>
              <Ionicons name="close" size={26} color="#000000" />
            </TouchableOpacity>
          </View>

          {effectiveUnreadCount > 0 && (
            <TouchableOpacity
              onPress={onMarkAllAsRead}
              style={styles.markAllButton}
              activeOpacity={0.7}
            >
              <Ionicons name="checkmark-done-outline" size={16} color="#2C2C2C" />
              <Text style={styles.markAllButtonText}>Marcar todas como lidas</Text>
            </TouchableOpacity>
          )}

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 20 }}>
            {list.length === 0 ? (
              <View style={styles.emptyNotificationsContainer}>
                <Ionicons name="notifications-off-outline" size={48} color="#CCCCCC" />
                <Text style={styles.emptyNotificationsText}>
                  Nenhuma notificação por aqui.
                </Text>
                {!isPremium && (
                  <Text style={styles.emptySubText}>
                    Assine o Premium para receber insights inteligentes de IA.
                  </Text>
                )}
              </View>
            ) : (
              list.map((item) => {
                const priorityKey = (item.priority && typeof item.priority === 'string')
                  ? item.priority.toLowerCase()
                  : 'medium';
                const bg = PRIORITY_BG[priorityKey] || PRIORITY_BG.medium;
                const accent = PRIORITY_ACCENT[priorityKey] || PRIORITY_ACCENT.medium;
                const priorityLabel = PRIORITY_LABEL[priorityKey] || PRIORITY_LABEL.medium;

                return (
                  <View
                    key={String(item.id)}
                    style={[
                      styles.notificationItem,
                      !item.read && styles.notificationItemUnread,
                      { backgroundColor: !item.read ? bg : '#FFFFFF' }
                    ]}
                  >
                    <View style={[styles.notificationLeftIcon, { borderColor: accent }]}>
                      {getTypeIcon(item)}
                    </View>

                    <View style={styles.notificationTextWrap}>
                      <View style={styles.notificationTitleRow}>
                        <Text
                          numberOfLines={2}
                          style={[
                            styles.notificationItemTitle,
                            !item.read && styles.notificationItemTitleUnread
                          ]}
                        >
                          {item.title || 'Notificação'}
                        </Text>
                      </View>

                      <Text
                        numberOfLines={3}
                        style={styles.notificationItemDescription}
                      >
                        {item.description || item.message || ''}
                      </Text>

                      <View style={styles.notificationMetaRow}>
                        <View style={styles.metaTagsRow}>
                          {renderTag(item, 'p', priorityLabel, accent, bg)}
                          {item.ai_generated && renderTag(item, 'ia', '✨ IA', '#1976D2', '#E3F2FD')}
                          {item.premium_only && renderTag(item, 'pr', 'PREMIUM', '#B8860B', '#FFF8E1')}
                        </View>
                        {(item.time || item.created_at) && (
                          <Text style={styles.notificationItemTime}>
                            {item.time || item.created_at}
                          </Text>
                        )}
                      </View>
                    </View>

                    {!item.read && (
                      <View
                        style={[styles.notificationDotActive, { backgroundColor: accent }]}
                      />
                    )}
                  </View>
                );
              })
            )}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end'
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#D9D9D9',
    alignSelf: 'center',
    marginBottom: 12
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8
  },
  modalTitleRow: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#000000',
    marginLeft: 8,
    marginRight: 10
  },
  headerBadge: {
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    paddingHorizontal: 6,
    backgroundColor: '#F44336',
    alignItems: 'center',
    justifyContent: 'center'
  },
  headerBadgeText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800'
  },
  notificationModalCard: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 30,
    maxHeight: '82%'
  },
  markAllButton: {
    alignSelf: 'flex-end',
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center'
  },
  markAllButtonText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#000000',
    marginLeft: 4,
    textDecorationLine: 'underline'
  },
  emptyNotificationsContainer: {
    alignItems: 'center',
    paddingVertical: 40
  },
  emptyNotificationsText: {
    textAlign: 'center',
    color: '#666666',
    fontSize: 14,
    marginTop: 12
  },
  emptySubText: {
    textAlign: 'center',
    color: '#AAAAAA',
    fontSize: 12,
    marginTop: 6,
    maxWidth: 280
  },
  notificationItem: {
    flexDirection: 'row',
    paddingVertical: 14,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
    borderRadius: 12,
    marginBottom: 8,
    alignItems: 'flex-start'
  },
  notificationItemUnread: {
    borderWidth: 1,
    borderColor: '#E8E8E8'
  },
  notificationLeftIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12
  },
  notificationTextWrap: {
    flex: 1,
    marginRight: 8
  },
  notificationTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  notificationItemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#444444',
    marginBottom: 4,
    flex: 1
  },
  notificationItemTitleUnread: {
    color: '#000000',
    fontWeight: '800'
  },
  notificationItemDescription: {
    fontSize: 12.5,
    color: '#555555',
    lineHeight: 18
  },
  notificationMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8
  },
  metaTagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    flex: 1
  },
  tag: {
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginRight: 6,
    marginBottom: 4
  },
  tagText: {
    fontSize: 10,
    fontWeight: '700'
  },
  notificationDotActive: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 10,
    marginLeft: 4
  },
  notificationItemTime: {
    fontSize: 10,
    color: '#999999',
    marginLeft: 4
  }
});

export default React.memo(NotificationsModal);
