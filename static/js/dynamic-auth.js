// This will be the main file that integrates with Web3 wallets for login/register
document.addEventListener('DOMContentLoaded', function() {
  console.log('Web3 wallet auth script loaded');
  
  // Initialize wallet connection UI only if we're on the login or register page
  const dynamicContainer = document.getElementById('dynamic-wallet-container');
  if (!dynamicContainer) {
    console.log('Wallet container not found');
    return;
  }
  console.log('Wallet container found');
  
  // Create a sign-in button immediately
  const signInButton = document.createElement('button');
  signInButton.className = 'btn btn-primary btn-block';
  signInButton.innerText = 'Connect Wallet';
  signInButton.onclick = function() {
    console.log('Connect wallet button clicked');
    showWalletOptions();
  };
  
  // Add the button to the container
  dynamicContainer.appendChild(signInButton);
  console.log('Connect wallet button added');
  
  // Show wallet connection options
  function showWalletOptions() {
    // Remove any existing UI
    const existingUI = document.getElementById('wallet-options-ui');
    if (existingUI) {
      existingUI.remove();
    }
    
    // Create wallet options UI
    const walletUI = document.createElement('div');
    walletUI.id = 'wallet-options-ui';
    walletUI.className = 'card mt-3';
    walletUI.innerHTML = `
      <div class="card-header bg-dark text-white">
        <div class="d-flex justify-content-between align-items-center">
          <h5 class="mb-0">Connect Wallet</h5>
          <button type="button" class="btn-close btn-close-white" id="close-wallet-ui"></button>
        </div>
      </div>
      <div class="card-body">
        <div class="list-group">
          <button class="list-group-item list-group-item-action d-flex align-items-center" id="connect-metamask">
            <img src="https://upload.wikimedia.org/wikipedia/commons/3/36/MetaMask_Fox.svg" alt="MetaMask" style="width: 30px; margin-right: 10px;">
            MetaMask
          </button>
          <button class="list-group-item list-group-item-action d-flex align-items-center" id="connect-walletconnect">
            <img src="https://seeklogo.com/images/W/walletconnect-logo-EE83B50C97-seeklogo.com.png" alt="WalletConnect" style="width: 30px; margin-right: 10px;">
            WalletConnect
          </button>
          <button class="list-group-item list-group-item-action d-flex align-items-center" id="connect-coinbase">
            <img src="https://upload.wikimedia.org/wikipedia/commons/1/1a/Coinbase.svg" alt="Coinbase Wallet" style="width: 30px; margin-right: 10px;">
            Coinbase Wallet
          </button>
        </div>
      </div>
    `;
    
    // Add the wallet UI to the container
    dynamicContainer.appendChild(walletUI);
    
    // Add event listeners for the wallet UI
    document.getElementById('close-wallet-ui').addEventListener('click', function() {
      walletUI.remove();
    });
    
    // Handle wallet connection clicks
    document.getElementById('connect-metamask').addEventListener('click', function() {
      connectWithWallet('metamask');
    });
    
    document.getElementById('connect-walletconnect').addEventListener('click', function() {
      connectWithWallet('walletconnect');
    });
    
    document.getElementById('connect-coinbase').addEventListener('click', function() {
      connectWithWallet('coinbase');
    });
  }
  
  // Connect with selected wallet
  async function connectWithWallet(walletType) {
    console.log(`Connecting with ${walletType}...`);
    
    // Remove the wallet UI
    const walletUI = document.getElementById('wallet-options-ui');
    if (walletUI) {
      walletUI.remove();
    }
    
    // Show loading state
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'alert alert-info mt-3';
    loadingDiv.innerHTML = `<div class="spinner-border spinner-border-sm me-2" role="status"></div> Connecting...`;
    dynamicContainer.appendChild(loadingDiv);
    
    try {
      let walletAddress;
      
      // Connect to the selected wallet
      if (walletType === 'metamask') {
        // Use our wallet utility to connect to MetaMask
        const connectResult = await YAPWallet.connect();
        
        if (!connectResult.success) {
          // If wallet needs to be installed, show installation options
          if (connectResult.needsInstall) {
            loadingDiv.remove();
            YAPWallet.showInstallOptions(dynamicContainer);
            return;
          }
          
          throw new Error(connectResult.error);
        }
        
        walletAddress = connectResult.walletAddress;
      } else if (walletType === 'walletconnect' || walletType === 'coinbase') {
        // For now, show a message that these are not implemented yet
        loadingDiv.className = 'alert alert-warning mt-3';
        loadingDiv.innerHTML = `
          <strong>Not Implemented</strong><br>
          ${walletType === 'walletconnect' ? 'WalletConnect' : 'Coinbase Wallet'} integration is coming soon. Please use MetaMask for now.
        `;
        
        // Add a back button
        const backButton = document.createElement('button');
        backButton.className = 'btn btn-primary mt-2';
        backButton.innerText = 'Back to Options';
        backButton.onclick = function() {
          loadingDiv.remove();
          showWalletOptions();
        };
        
        loadingDiv.appendChild(backButton);
        return;
      } else {
        throw new Error(`Unsupported wallet type: ${walletType}`);
      }
      
      // Get CSRF token from meta tag
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
      
      // Send the wallet address to the backend for authentication
      const response = await fetch('/api/auth/dynamic/callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({ token: `${walletType}_auth`, walletAddress: walletAddress })
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        // Show success message
        loadingDiv.className = 'alert alert-success mt-3';
        loadingDiv.innerHTML = `
          <strong>Wallet Connected!</strong><br>
          Address: ${walletAddress.substring(0, 6)}...${walletAddress.substring(38)}<br>
          Redirecting to dashboard...
        `;
        
        // Redirect to exercises page
        setTimeout(function() {
          window.location.href = data.redirectUrl || '/exercises';
        }, 2000);
      } else {
        throw new Error(data.error || 'Failed to authenticate with wallet');
      }
    } catch (error) {
      console.error(`Error connecting with ${walletType}:`, error);
      
      // Show error message
      loadingDiv.className = 'alert alert-danger mt-3';
      loadingDiv.innerHTML = `<strong>Error:</strong> ${error.message || `Failed to connect with ${walletType}`}`;
      
      // Add a retry button
      const retryButton = document.createElement('button');
      retryButton.className = 'btn btn-primary mt-2';
      retryButton.innerText = 'Try Again';
      retryButton.onclick = function() {
        loadingDiv.remove();
        showWalletOptions();
      };
      
      loadingDiv.appendChild(retryButton);
    }
  }
}); 