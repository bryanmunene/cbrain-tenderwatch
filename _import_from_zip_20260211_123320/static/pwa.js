// TenderWatch PWA Installation & Notification Manager
(function() {
  'use strict';
  
  // Configuration
  const CONFIG = {
    SW_PATH: '/static/service-worker.js',
    STORAGE_KEY: 'tenderwatch_settings',
    DEFAULT_SCAN_HOUR: 8, // 8 AM
    MIN_INTERVAL_HOURS: 24
  };
  
  // State
  let deferredPrompt = null;
  let swRegistration = null;
  
  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  function init() {
    console.log('[PWA] Initializing TenderWatch PWA...');
    registerServiceWorker();
    setupInstallPrompt();
    setupNotificationScheduler();
    injectInstallUI();
  }
  
  // Register Service Worker
  async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      console.log('[PWA] Service workers not supported');
      return;
    }
    
    try {
      swRegistration = await navigator.serviceWorker.register(CONFIG.SW_PATH, {
        scope: '/'
      });
      console.log('[PWA] Service Worker registered:', swRegistration.scope);
      
      // Check for updates
      swRegistration.addEventListener('updatefound', () => {
        console.log('[PWA] New service worker available');
      });
      
      // Setup periodic sync if available
      if ('periodicSync' in swRegistration) {
        try {
          await swRegistration.periodicSync.register('daily-tender-scan', {
            minInterval: 24 * 60 * 60 * 1000 // 24 hours
          });
          console.log('[PWA] Periodic sync registered');
        } catch (e) {
          console.log('[PWA] Periodic sync not available:', e);
        }
      }
    } catch (error) {
      console.error('[PWA] Service Worker registration failed:', error);
    }
  }
  
  // Handle install prompt
  function setupInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      console.log('[PWA] Install prompt available');
      e.preventDefault();
      deferredPrompt = e;
      showInstallButton();
    });
    
    window.addEventListener('appinstalled', () => {
      console.log('[PWA] App installed successfully!');
      deferredPrompt = null;
      hideInstallButton();
      saveSettings({ installed: true, installedAt: new Date().toISOString() });
    });
  }
  
  // Setup notification scheduler
  function setupNotificationScheduler() {
    const settings = loadSettings();
    
    if (settings.notificationsEnabled && settings.scanHour !== undefined) {
      scheduleNextNotification(settings.scanHour);
    }
  }
  
  // Schedule notification for specific hour
  function scheduleNextNotification(hour) {
    const now = new Date();
    let nextScan = new Date(now);
    nextScan.setHours(hour, 0, 0, 0);
    
    // If time has passed today, schedule for tomorrow
    if (nextScan <= now) {
      nextScan.setDate(nextScan.getDate() + 1);
    }
    
    const delay = nextScan.getTime() - now.getTime();
    console.log(`[PWA] Next notification scheduled in ${Math.round(delay / 1000 / 60)} minutes`);
    
    // Clear any existing timer
    if (window.tenderWatchTimer) {
      clearTimeout(window.tenderWatchTimer);
    }
    
    // Set timer
    window.tenderWatchTimer = setTimeout(() => {
      sendDailyNotification();
      // Reschedule for next day
      scheduleNextNotification(hour);
    }, delay);
    
    // Also save to localStorage for persistence
    saveSettings({ 
      nextScanTime: nextScan.toISOString(),
      scanHour: hour 
    });
  }
  
  // Send daily notification
  async function sendDailyNotification() {
    if (!('Notification' in window)) {
      console.log('[PWA] Notifications not supported');
      return;
    }
    
    if (Notification.permission !== 'granted') {
      console.log('[PWA] Notification permission not granted');
      return;
    }
    
    try {
      // Try using service worker notification first
      if (swRegistration) {
        await swRegistration.showNotification('TenderWatch Daily Scan', {
          body: '🔔 Time to check for new tender opportunities! Tap to scan now.',
          icon: '/static/icons/icon-192.png',
          badge: '/static/icons/icon-72.png',
          tag: 'daily-reminder',
          requireInteraction: true,
          vibrate: [200, 100, 200],
          actions: [
            { action: 'scan', title: '🔍 Scan Now' },
            { action: 'dismiss', title: '✕ Later' }
          ]
        });
      } else {
        // Fallback to basic notification
        new Notification('TenderWatch Daily Scan', {
          body: '🔔 Time to check for new tender opportunities!',
          icon: '/static/icons/icon-192.png',
          tag: 'daily-reminder'
        });
      }
      console.log('[PWA] Daily notification sent');
    } catch (error) {
      console.error('[PWA] Failed to send notification:', error);
    }
  }
  
  // Request notification permission
  async function requestNotificationPermission() {
    if (!('Notification' in window)) {
      alert('Notifications are not supported in this browser');
      return false;
    }
    
    if (Notification.permission === 'granted') {
      return true;
    }
    
    if (Notification.permission === 'denied') {
      alert('Notifications are blocked. Please enable them in your browser settings.');
      return false;
    }
    
    const permission = await Notification.requestPermission();
    return permission === 'granted';
  }
  
  // Show install button
  function showInstallButton() {
    const btn = document.getElementById('pwa-install-btn');
    if (btn) btn.style.display = 'block';
  }
  
  // Hide install button
  function hideInstallButton() {
    const btn = document.getElementById('pwa-install-btn');
    if (btn) btn.style.display = 'none';
  }
  
  // Trigger install prompt
  async function installApp() {
    if (!deferredPrompt) {
      console.log('[PWA] Install prompt not available');
      return false;
    }
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log('[PWA] Install outcome:', outcome);
    deferredPrompt = null;
    return outcome === 'accepted';
  }
  
  // Inject install UI into Streamlit
  function injectInstallUI() {
    // Wait for Streamlit to load
    const checkStreamlit = setInterval(() => {
      const mainContent = document.querySelector('[data-testid="stAppViewContainer"]');
      if (mainContent && !document.getElementById('pwa-floating-btn')) {
        clearInterval(checkStreamlit);
        createFloatingInstallButton();
      }
    }, 1000);
  }
  
  // Create floating install button
  function createFloatingInstallButton() {
    const floatingBtn = document.createElement('div');
    floatingBtn.id = 'pwa-floating-btn';
    floatingBtn.innerHTML = `
      <style>
        #pwa-floating-btn {
          position: fixed;
          bottom: 20px;
          right: 20px;
          z-index: 9999;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .pwa-btn {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          transition: transform 0.2s, box-shadow 0.2s;
        }
        .pwa-btn:hover {
          transform: scale(1.1);
          box-shadow: 0 6px 16px rgba(0,0,0,0.4);
        }
        #pwa-install-btn {
          background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
          color: white;
          display: none;
        }
        #pwa-notify-btn {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          color: white;
        }
        .pwa-tooltip {
          position: absolute;
          right: 70px;
          background: #1e293b;
          color: white;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 12px;
          white-space: nowrap;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s;
        }
        .pwa-btn:hover .pwa-tooltip {
          opacity: 1;
        }
      </style>
      <button id="pwa-install-btn" class="pwa-btn" onclick="window.TenderWatchPWA.install()">
        📲
        <span class="pwa-tooltip">Install App</span>
      </button>
      <button id="pwa-notify-btn" class="pwa-btn" onclick="window.TenderWatchPWA.setupNotifications()">
        🔔
        <span class="pwa-tooltip">Daily Notifications</span>
      </button>
    `;
    document.body.appendChild(floatingBtn);
    
    // Check if install is available
    if (deferredPrompt) {
      showInstallButton();
    }
    
    // Check if already installed (standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      hideInstallButton();
    }
  }
  
  // Setup notifications with time picker
  async function setupNotifications() {
    const hasPermission = await requestNotificationPermission();
    if (!hasPermission) return;
    
    const settings = loadSettings();
    const currentHour = settings.scanHour || CONFIG.DEFAULT_SCAN_HOUR;
    
    const hour = prompt(
      `Set daily scan notification time (0-23 hours):\n\nCurrent: ${currentHour}:00\n\nExample: Enter 8 for 8:00 AM, 18 for 6:00 PM`,
      currentHour
    );
    
    if (hour === null) return; // Cancelled
    
    const parsedHour = parseInt(hour, 10);
    if (isNaN(parsedHour) || parsedHour < 0 || parsedHour > 23) {
      alert('Please enter a valid hour (0-23)');
      return;
    }
    
    saveSettings({ 
      notificationsEnabled: true, 
      scanHour: parsedHour 
    });
    
    scheduleNextNotification(parsedHour);
    
    // Send test notification
    if (swRegistration) {
      await swRegistration.showNotification('TenderWatch Notifications Enabled', {
        body: `✅ You'll receive daily scan reminders at ${parsedHour}:00`,
        icon: '/static/icons/icon-192.png',
        tag: 'setup-confirmation'
      });
    } else {
      new Notification('TenderWatch Notifications Enabled', {
        body: `✅ You'll receive daily scan reminders at ${parsedHour}:00`,
        icon: '/static/icons/icon-192.png'
      });
    }
    
    alert(`✅ Daily notifications set for ${parsedHour}:00!\n\nYou'll receive a reminder to scan for new tenders.`);
  }
  
  // Load settings from localStorage
  function loadSettings() {
    try {
      const saved = localStorage.getItem(CONFIG.STORAGE_KEY);
      return saved ? JSON.parse(saved) : {};
    } catch (e) {
      return {};
    }
  }
  
  // Save settings to localStorage
  function saveSettings(newSettings) {
    try {
      const current = loadSettings();
      const updated = { ...current, ...newSettings };
      localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(updated));
      return updated;
    } catch (e) {
      console.error('[PWA] Failed to save settings:', e);
      return {};
    }
  }
  
  // Expose API globally
  window.TenderWatchPWA = {
    install: installApp,
    setupNotifications: setupNotifications,
    requestPermission: requestNotificationPermission,
    sendNotification: sendDailyNotification,
    getSettings: loadSettings,
    saveSettings: saveSettings,
    scheduleNotification: scheduleNextNotification
  };
  
})();
