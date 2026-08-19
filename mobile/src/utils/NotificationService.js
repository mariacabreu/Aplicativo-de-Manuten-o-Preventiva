import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import API_BASE_URL from '../api';

const POLL_INTERVAL_FREE_MS = 5 * 60 * 1000;
const POLL_INTERVAL_PREMIUM_MS = 2 * 60 * 1000;
const TRIGGER_MIN_INTERVAL_MS = 30 * 60 * 1000;

const STORAGE_KEYS = {
  PREFS: '@amp:notif_prefs',
  LAST_TRIGGER: '@amp:last_periodic_trigger',
  LAST_KNOWN_COUNT: '@amp:last_unread_count',
};

class NotificationServiceClass {
  constructor() {
    this.listeners = new Set();
    this.intervalId = null;
    this.userId = null;
    this.currentUnread = 0;
    this.currentNotifications = [];
    this.isPremium = false;
    this.prefs = null;
    this._bootstrapped = false;
  }

  async bootstrap(userId, isPremium = false) {
    if (this._bootstrapped && this.userId === userId) return;
    this.userId = userId;
    this.isPremium = isPremium;
    try {
      const cachedPrefs = await AsyncStorage.getItem(STORAGE_KEYS.PREFS);
      if (cachedPrefs) this.prefs = JSON.parse(cachedPrefs);
      const cachedCount = await AsyncStorage.getItem(STORAGE_KEYS.LAST_KNOWN_COUNT);
      if (cachedCount) this.currentUnread = parseInt(cachedCount, 10) || 0;
    } catch (e) {
      console.warn('[NotifSvc] cache load failed:', e);
    }
    this._bootstrapped = true;
    this.startPolling();
  }

  subscribe(callback) {
    this.listeners.add(callback);
    callback({
      unreadCount: this.getEffectiveUnread(),
      notifications: this.currentNotifications,
      prefs: this.prefs,
    });
    return () => this.listeners.delete(callback);
  }

  _emit(event) {
    const payload = {
      unreadCount: this.getEffectiveUnread(),
      notifications: this.currentNotifications,
      prefs: this.prefs,
      ...event,
    };
    this.listeners.forEach((l) => {
      try { l(payload); } catch (e) { console.warn('[NotifSvc] listener error:', e); }
    });
  }

  getEffectiveUnread() {
    if (this.prefs && this.prefs.notifications_enabled === false) {
      return 0;
    }
    return this.currentUnread || 0;
  }

  isPolling() {
    return this.intervalId != null;
  }

  startPolling() {
    if (!this.userId) return;
    this.stopPolling();
    const interval = this.isPremium ? POLL_INTERVAL_PREMIUM_MS : POLL_INTERVAL_FREE_MS;
    this.fetchNotifications(true).catch(() => {});
    this.intervalId = setInterval(() => {
      this.fetchNotifications().catch(() => {});
      this.attemptPeriodicTrigger().catch(() => {});
    }, interval);
  }

  stopPolling() {
    if (this.intervalId != null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  async _getLastTrigger() {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEYS.LAST_TRIGGER);
      return raw ? parseInt(raw, 10) || 0 : 0;
    } catch {
      return 0;
    }
  }

  async _setLastTrigger(ts) {
    try { await AsyncStorage.setItem(STORAGE_KEYS.LAST_TRIGGER, String(ts)); } catch {}
  }

  async attemptPeriodicTrigger({ force = false } = {}) {
    if (!this.userId) return { skipped: true };
    const now = Date.now();
    const last = await this._getLastTrigger();
    if (!force && (now - last) < TRIGGER_MIN_INTERVAL_MS) {
      return { skipped: true, reason: 'local-throttle' };
    }
    try {
      const res = await axios.post(
        `${API_BASE_URL}/user/notifications/${this.userId}/periodic-check`,
        { force: !!force },
        { timeout: 25000, headers: { 'Content-Type': 'application/json' } },
      );
      await this._setLastTrigger(now);
      if (res.data && typeof res.data.unread_count === 'number') {
        this.currentUnread = res.data.unread_count;
        await AsyncStorage.setItem(STORAGE_KEYS.LAST_KNOWN_COUNT, String(this.currentUnread));
        this._emit({ source: 'periodic-trigger' });
      }
      return res.data || {};
    } catch (e) {
      console.warn('[NotifSvc] periodic trigger failed:', e?.message || e);
      return { error: true, message: e?.message };
    }
  }

  async fetchNotifications({ forceRefresh = false } = {}) {
    if (!this.userId) return { notifications: [], unread_count: 0 };
    try {
      const url = forceRefresh
        ? `${API_BASE_URL}/user/notifications/${this.userId}?refresh=1`
        : `${API_BASE_URL}/user/notifications/${this.userId}`;
      const res = await axios.get(url, { timeout: 20000 });
      const list = Array.isArray(res.data?.notifications) ? res.data.notifications : [];
      const unread = typeof res.data?.unread_count === 'number'
        ? res.data.unread_count
        : list.filter((n) => !n.read).length;
      this.currentNotifications = list;
      this.currentUnread = unread;
      try { await AsyncStorage.setItem(STORAGE_KEYS.LAST_KNOWN_COUNT, String(unread)); } catch {}
      this._emit({ source: 'fetch' });
      return { notifications: list, unread_count: unread, raw: res.data };
    } catch (e) {
      console.warn('[NotifSvc] fetch failed:', e?.message || e);
      throw e;
    }
  }

  async markAllAsRead() {
    if (!this.userId) return;
    try {
      this.currentNotifications = this.currentNotifications.map((n) => ({ ...n, read: true }));
      this.currentUnread = 0;
      try { await AsyncStorage.setItem(STORAGE_KEYS.LAST_KNOWN_COUNT, '0'); } catch {}
      this._emit({ source: 'markAll' });
      await axios.patch(
        `${API_BASE_URL}/user/notifications/${this.userId}/read-all`,
        {},
        { timeout: 15000 },
      );
    } catch (e) {
      console.warn('[NotifSvc] mark-all failed:', e?.message || e);
    }
  }

  async regeneratePremiumInsights() {
    if (!this.userId) return { error: true };
    try {
      await axios.post(`${API_BASE_URL}/user/notifications/${this.userId}/ai/generate`, {}, { timeout: 60000 });
      await this._setLastTrigger(0);
      return this.fetchNotifications({ forceRefresh: true });
    } catch (e) {
      console.warn('[NotifSvc] regenerate AI failed:', e?.message || e);
      throw e;
    }
  }

  async fetchPreferences() {
    if (!this.userId) return null;
    try {
      const res = await axios.get(`${API_BASE_URL}/user/${this.userId}/notification-preferences`, { timeout: 15000 });
      this.prefs = res.data?.preferences || this.prefs || {};
      if ('is_premium' in (res.data || {})) {
        this.isPremium = !!res.data.is_premium;
      }
      try { await AsyncStorage.setItem(STORAGE_KEYS.PREFS, JSON.stringify(this.prefs)); } catch {}
      this._emit({ source: 'prefs' });
      return this.prefs;
    } catch (e) {
      console.warn('[NotifSvc] fetch prefs failed:', e?.message || e);
      return this.prefs;
    }
  }

  async savePreferences(newPrefs) {
    if (!this.userId) return null;
    try {
      const payload = { ...this.prefs, ...newPrefs };
      const res = await axios.put(
        `${API_BASE_URL}/user/${this.userId}/notification-preferences`,
        payload,
        { timeout: 15000, headers: { 'Content-Type': 'application/json' } },
      );
      this.prefs = res.data?.preferences || payload;
      try { await AsyncStorage.setItem(STORAGE_KEYS.PREFS, JSON.stringify(this.prefs)); } catch {}
      this._emit({ source: 'save-prefs' });
      return this.prefs;
    } catch (e) {
      console.warn('[NotifSvc] save prefs failed:', e?.message || e);
      throw e;
    }
  }

  reset() {
    this.stopPolling();
    this.listeners.clear();
    this.userId = null;
    this.currentUnread = 0;
    this.currentNotifications = [];
    this.prefs = null;
    this._bootstrapped = false;
  }
}

export const NotificationService = new NotificationServiceClass();
export default NotificationService;
