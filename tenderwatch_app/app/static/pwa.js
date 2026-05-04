// Progressive Web App Registration and Install Handler

// Register service worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/service-worker.js')
      .then((registration) => {
        console.log('Service Worker registered successfully:', registration.scope);
      })
      .catch((error) => {
        console.log('Service Worker registration failed:', error);
      });
  });
}

// Install prompt handler
let deferredPrompt;
const installButton = document.getElementById('install-button');

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault();
  // Stash the event so it can be triggered later
  deferredPrompt = e;
  
  // Show install button if it exists
  if (installButton) {
    installButton.style.display = 'block';
  }
  
  // Show install banner
  showInstallBanner();
});

function showInstallBanner() {
  const banner = document.createElement('div');
  banner.id = 'install-banner';
  banner.className = 'alert alert-dismissible fade show position-fixed bottom-0 start-0 end-0 m-3 shadow-lg';
  banner.style.zIndex = '9999';
  banner.style.background = '#fff8f1';
  banner.style.color = '#1e140e';
  banner.style.border = '1px solid #d7c3ae';
  banner.innerHTML = `
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    <div class="d-flex align-items-center">
      <i class="fas fa-mobile-alt fa-2x me-3"></i>
      <div class="flex-grow-1">
        <strong>Install TenderWatch</strong>
        <p class="mb-0 small">Install this app on your device for quick access and offline support!</p>
      </div>
      <button class="btn ms-3" id="install-banner-button" style="background:#8f4a2f;color:#fff8f1;border-color:#6f3825;">
        <i class="fas fa-download"></i> Install
      </button>
    </div>
  `;
  
  document.body.appendChild(banner);
  
  // Handle install button click
  document.getElementById('install-banner-button').addEventListener('click', installApp);
}

async function installApp() {
  if (!deferredPrompt) {
    console.log('Install prompt not available');
    return;
  }
  
  // Show the install prompt
  deferredPrompt.prompt();
  
  // Wait for the user to respond to the prompt
  const { outcome } = await deferredPrompt.userChoice;
  console.log(`User response to install prompt: ${outcome}`);
  
  // Clear the deferredPrompt
  deferredPrompt = null;
  
  // Hide install banner
  const banner = document.getElementById('install-banner');
  if (banner) {
    banner.remove();
  }
  
  // Hide install button
  if (installButton) {
    installButton.style.display = 'none';
  }
}

// Handle successful installation
window.addEventListener('appinstalled', () => {
  console.log('TenderWatch installed successfully!');
  deferredPrompt = null;
  
  // Show success message
  const successToast = document.createElement('div');
  successToast.className = 'toast position-fixed top-0 end-0 m-3';
  successToast.innerHTML = `
    <div class="toast-header bg-success text-white">
      <i class="fas fa-check-circle me-2"></i>
      <strong class="me-auto">Success!</strong>
      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
    </div>
    <div class="toast-body">
      TenderWatch has been installed! You can now access it from your home screen.
    </div>
  `;
  document.body.appendChild(successToast);
  
  const toast = new bootstrap.Toast(successToast);
  toast.show();
});

// Check if already installed (standalone mode)
if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
  console.log('Running as installed PWA');
  document.body.classList.add('pwa-installed');
}

// Online/Offline status
window.addEventListener('online', () => {
  console.log('Back online');
  showConnectionStatus('online');
});

window.addEventListener('offline', () => {
  console.log('Gone offline');
  showConnectionStatus('offline');
});

function showConnectionStatus(status) {
  const statusBar = document.getElementById('connection-status');
  if (!statusBar) {
    const bar = document.createElement('div');
    bar.id = 'connection-status';
    bar.className = `alert ${status === 'online' ? 'alert-success' : 'alert-warning'} position-fixed top-0 start-0 end-0 m-0 text-center`;
    bar.style.zIndex = '10000';
    bar.innerHTML = status === 'online' 
      ? '<i class="fas fa-wifi"></i> Back online' 
      : '<i class="fas fa-wifi-slash"></i> You are offline';
    document.body.insertBefore(bar, document.body.firstChild);
    
    setTimeout(() => bar.remove(), 3000);
  }
}

// Background sync (if supported)
if ('serviceWorker' in navigator && 'SyncManager' in window) {
  navigator.serviceWorker.ready.then((registration) => {
    // Register background sync
    return registration.sync.register('sync-tenders');
  }).catch((error) => {
    console.log('Background sync registration failed:', error);
  });
}
