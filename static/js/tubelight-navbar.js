// Tubelight NavBar for Flask
document.addEventListener('DOMContentLoaded', function() {
  // Define the navigation items
  const navItems = [
    { name: 'Home', url: '/', icon: 'bi-house' },
    { name: 'Vocabulary', url: '/vocabulary-practice', icon: 'bi-book' },
    { name: 'Conversation', url: '/conversation-practice', icon: 'bi-chat-dots' },
    { name: 'Speaking', url: '/speaking-practice', icon: 'bi-mic' }
  ];
  
  // Check if user is authenticated
  const isAuthenticated = document.querySelector('meta[name="user-authenticated"]')?.content === 'true';
  if (isAuthenticated) {
    navItems.push({ name: 'Profile', url: '/profile', icon: 'bi-person' });
  }

  // Create the navbar container
  const navbar = document.createElement('div');
  navbar.className = 'tubelight-navbar fixed-bottom d-md-none';
  
  // Create the navbar content
  const navbarContent = document.createElement('div');
  navbarContent.className = 'navbar-content d-flex justify-content-around bg-dark bg-opacity-75 border border-secondary rounded-pill shadow-lg py-2 px-3 mx-auto';
  navbarContent.style.maxWidth = '90%';
  navbarContent.style.backdropFilter = 'blur(10px)';
  navbarContent.style.WebkitBackdropFilter = 'blur(10px)';
  navbarContent.style.marginBottom = '1.5rem';
  
  // Get the current path
  const currentPath = window.location.pathname;
  
  // Create the navbar items
  navItems.forEach(item => {
    const isActive = currentPath === item.url || 
                    (item.url !== '/' && currentPath.startsWith(item.url));
    
    const navItem = document.createElement('a');
    navItem.href = item.url;
    navItem.className = `nav-item d-flex flex-column align-items-center px-4 py-2 rounded-pill ${isActive ? 'active bg-primary bg-opacity-25 text-primary' : 'text-light'}`;
    navItem.style.textDecoration = 'none';
    navItem.style.position = 'relative';
    navItem.style.transition = 'all 0.3s ease';
    navItem.style.margin = '0 2px';
    
    const icon = document.createElement('i');
    icon.className = `bi ${item.icon} ${isActive ? 'text-primary' : 'text-light'}`;
    icon.style.fontSize = '1.2rem';
    
    const text = document.createElement('span');
    text.className = 'd-none d-md-inline small mt-1';
    text.textContent = item.name;
    
    navItem.appendChild(icon);
    navItem.appendChild(text);
    
    // Add tubelight effect for active item
    if (isActive) {
      const tubelight = document.createElement('div');
      tubelight.className = 'tubelight-effect';
      tubelight.style.position = 'absolute';
      tubelight.style.top = '-8px';
      tubelight.style.left = '50%';
      tubelight.style.transform = 'translateX(-50%)';
      tubelight.style.width = '20px';
      tubelight.style.height = '3px';
      tubelight.style.backgroundColor = 'var(--bs-primary)';
      tubelight.style.borderRadius = '3px 3px 0 0';
      
      // Add glow effect
      const glow = document.createElement('div');
      glow.style.position = 'absolute';
      glow.style.width = '30px';
      glow.style.height = '10px';
      glow.style.backgroundColor = 'var(--bs-primary)';
      glow.style.opacity = '0.3';
      glow.style.filter = 'blur(8px)';
      glow.style.borderRadius = '50%';
      glow.style.top = '-5px';
      glow.style.left = '50%';
      glow.style.transform = 'translateX(-50%)';
      
      tubelight.appendChild(glow);
      navItem.appendChild(tubelight);
    }
    
    navbarContent.appendChild(navItem);
  });
  
  navbar.appendChild(navbarContent);
  
  // Create desktop version (top navbar)
  const desktopNavbar = document.createElement('div');
  desktopNavbar.className = 'tubelight-navbar-desktop d-none d-md-block fixed-top';
  
  // Create desktop navbar content with logo and user info
  const desktopNavbarContent = document.createElement('div');
  desktopNavbarContent.className = 'd-flex justify-content-between align-items-center bg-dark bg-opacity-75 border border-secondary rounded-pill shadow-lg py-2 px-4 mx-auto mt-4';
  desktopNavbarContent.style.maxWidth = '95%';
  desktopNavbarContent.style.backdropFilter = 'blur(10px)';
  desktopNavbarContent.style.WebkitBackdropFilter = 'blur(10px)';
  
  // Create logo section
  const logoSection = document.createElement('a');
  logoSection.href = '/';
  logoSection.className = 'text-decoration-none d-flex align-items-center';
  
  const logoSpan = document.createElement('span');
  logoSpan.className = 'yap-logo';
  logoSpan.textContent = 'YAP';
  
  logoSection.appendChild(logoSpan);
  desktopNavbarContent.appendChild(logoSection);
  
  // Create navigation section
  const navSection = document.createElement('div');
  navSection.className = 'd-flex justify-content-center';
  
  // Add navigation items to desktop navbar
  navItems.forEach(item => {
    const isActive = currentPath === item.url || 
                    (item.url !== '/' && currentPath.startsWith(item.url));
    
    const navItem = document.createElement('a');
    navItem.href = item.url;
    navItem.className = `nav-item d-flex align-items-center px-4 py-2 rounded-pill mx-2 ${isActive ? 'active bg-primary bg-opacity-25 text-primary' : 'text-light'}`;
    navItem.style.textDecoration = 'none';
    navItem.style.position = 'relative';
    navItem.style.transition = 'all 0.3s ease';
    
    const icon = document.createElement('i');
    icon.className = `bi ${item.icon} ${isActive ? 'text-primary' : 'text-light'} me-2`;
    icon.style.fontSize = '1rem';
    
    const text = document.createElement('span');
    text.className = 'small';
    text.textContent = item.name;
    
    navItem.appendChild(icon);
    navItem.appendChild(text);
    
    // Add tubelight effect for active item
    if (isActive) {
      const tubelight = document.createElement('div');
      tubelight.className = 'tubelight-effect';
      tubelight.style.position = 'absolute';
      tubelight.style.top = '-8px';
      tubelight.style.left = '50%';
      tubelight.style.transform = 'translateX(-50%)';
      tubelight.style.width = '20px';
      tubelight.style.height = '3px';
      tubelight.style.backgroundColor = 'var(--bs-primary)';
      tubelight.style.borderRadius = '3px 3px 0 0';
      
      // Add glow effect
      const glow = document.createElement('div');
      glow.style.position = 'absolute';
      glow.style.width = '30px';
      glow.style.height = '10px';
      glow.style.backgroundColor = 'var(--bs-primary)';
      glow.style.opacity = '0.3';
      glow.style.filter = 'blur(8px)';
      glow.style.borderRadius = '50%';
      glow.style.top = '-5px';
      glow.style.left = '50%';
      glow.style.transform = 'translateX(-50%)';
      
      tubelight.appendChild(glow);
      navItem.appendChild(tubelight);
    }
    
    navSection.appendChild(navItem);
  });
  
  desktopNavbarContent.appendChild(navSection);
  
  // Create user info section
  const userSection = document.createElement('div');
  userSection.className = 'd-flex align-items-center gap-2';
  
  if (isAuthenticated) {
    // Get username from meta tag
    const username = document.querySelector('meta[name="username"]')?.content;
    
    // Add language badge
    const targetLanguage = document.querySelector('meta[name="target-language"]')?.content;
    if (targetLanguage) {
      // Map language codes to full names
      const languageNames = {
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'ru': 'Russian'
      };
      
      const langBadge = document.createElement('div');
      langBadge.className = 'language-badge';
      langBadge.dataset.lang = targetLanguage;
      
      const langIcon = document.createElement('i');
      langIcon.className = 'bi bi-translate';
      
      langBadge.appendChild(langIcon);
      langBadge.appendChild(document.createTextNode(' Learning ' + (languageNames[targetLanguage] || targetLanguage)));
      
      userSection.appendChild(langBadge);
    }
    
    // Create user dropdown
    const userDropdown = document.createElement('div');
    userDropdown.className = 'dropdown';
    
    const dropdownToggle = document.createElement('a');
    dropdownToggle.className = 'btn btn-outline-secondary dropdown-toggle';
    dropdownToggle.href = '#';
    dropdownToggle.id = 'profileDropdown';
    dropdownToggle.role = 'button';
    dropdownToggle.setAttribute('data-bs-toggle', 'dropdown');
    dropdownToggle.setAttribute('aria-expanded', 'false');
    
    const userIcon = document.createElement('i');
    userIcon.className = 'bi bi-person-circle';
    
    dropdownToggle.appendChild(userIcon);
    if (username) {
      dropdownToggle.appendChild(document.createTextNode(' ' + username));
    }
    
    userDropdown.appendChild(dropdownToggle);
    
    // Create dropdown menu
    const dropdownMenu = document.createElement('ul');
    dropdownMenu.className = 'dropdown-menu dropdown-menu-end';
    dropdownMenu.setAttribute('aria-labelledby', 'profileDropdown');
    
    // Profile link
    const profileItem = document.createElement('li');
    const profileLink = document.createElement('a');
    profileLink.className = 'dropdown-item';
    profileLink.href = '/profile';
    
    const profileIcon = document.createElement('i');
    profileIcon.className = 'bi bi-person';
    
    profileLink.appendChild(profileIcon);
    profileLink.appendChild(document.createTextNode(' Profile'));
    profileItem.appendChild(profileLink);
    dropdownMenu.appendChild(profileItem);
    
    // Wallet badge if connected
    const walletConnected = document.querySelector('.wallet-badge');
    if (walletConnected) {
      const walletItem = document.createElement('li');
      const walletSpan = document.createElement('span');
      walletSpan.className = 'dropdown-item';
      
      const walletBadge = document.createElement('span');
      walletBadge.className = 'wallet-badge';
      
      const walletIcon = document.createElement('i');
      walletIcon.className = 'bi bi-wallet-fill';
      
      walletBadge.appendChild(walletIcon);
      walletBadge.appendChild(document.createTextNode(' Wallet Connected'));
      
      walletSpan.appendChild(walletBadge);
      walletItem.appendChild(walletSpan);
      dropdownMenu.appendChild(walletItem);
    }
    
    // Divider
    const divider = document.createElement('li');
    const hr = document.createElement('hr');
    hr.className = 'dropdown-divider';
    divider.appendChild(hr);
    dropdownMenu.appendChild(divider);
    
    // Logout link
    const logoutItem = document.createElement('li');
    const logoutLink = document.createElement('a');
    logoutLink.className = 'dropdown-item';
    logoutLink.href = '/logout';
    
    const logoutIcon = document.createElement('i');
    logoutIcon.className = 'bi bi-box-arrow-right';
    
    logoutLink.appendChild(logoutIcon);
    logoutLink.appendChild(document.createTextNode(' Logout'));
    logoutItem.appendChild(logoutLink);
    dropdownMenu.appendChild(logoutItem);
    
    userDropdown.appendChild(dropdownMenu);
    userSection.appendChild(userDropdown);
  } else {
    // Add login and register buttons for unauthenticated users
    const loginLink = document.createElement('a');
    loginLink.href = '/login';
    loginLink.className = 'btn btn-outline-primary me-2';
    loginLink.textContent = 'Login';
    
    const registerLink = document.createElement('a');
    registerLink.href = '/register';
    registerLink.className = 'btn btn-primary';
    registerLink.textContent = 'Register';
    
    userSection.appendChild(loginLink);
    userSection.appendChild(registerLink);
  }
  
  desktopNavbarContent.appendChild(userSection);
  desktopNavbar.appendChild(desktopNavbarContent);
  
  // Add both navbars to the document
  document.body.appendChild(navbar);
  document.body.appendChild(desktopNavbar);
  
  // Add CSS for the navbar
  const style = document.createElement('style');
  style.textContent = `
    .tubelight-navbar, .tubelight-navbar-desktop {
      z-index: 1030;
      width: 100%;
      text-align: center;
    }
    
    .tubelight-navbar .navbar-content, .tubelight-navbar-desktop .navbar-content {
      display: inline-flex;
    }
    
    .tubelight-navbar .nav-item:hover, .tubelight-navbar-desktop .nav-item:hover {
      color: var(--bs-primary) !important;
    }
    
    .tubelight-navbar .nav-item:hover i, .tubelight-navbar-desktop .nav-item:hover i {
      color: var(--bs-primary) !important;
    }
    
    /* Add padding to body to account for fixed navbars */
    body {
      padding-bottom: 60px;
      padding-top: 60px;
    }
    
    /* Language badge styles */
    .language-badge {
      background-color: #007bff;
      color: white;
      padding: 5px 10px;
      border-radius: 20px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.875rem;
    }
    
    /* Wallet badge styles */
    .wallet-badge {
      background-color: #28a745;
      color: white;
      padding: 5px 10px;
      border-radius: 20px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.875rem;
    }
    
    /* YAP logo styles */
    .yap-logo {
      font-size: 1.5rem;
      font-weight: bold;
      color: #fff;
      background-color: #6f42c1;
      padding: 5px 10px;
      border-radius: 5px;
      display: inline-block;
    }
  `;
  
  document.head.appendChild(style);
});