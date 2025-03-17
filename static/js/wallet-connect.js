/**
 * Wallet connection utilities for YAP
 */

// Main wallet connection function
async function connectWallet() {
    try {
        // Check if MetaMask is installed
        if (!window.ethereum || !window.ethereum.isMetaMask) {
            return {
                success: false,
                error: 'MetaMask is not installed',
                needsInstall: true
            };
        }
        
        // Request account access
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        const walletAddress = accounts[0];
        
        if (!walletAddress) {
            return {
                success: false,
                error: 'No account selected in MetaMask'
            };
        }
        
        console.log('Connected to MetaMask:', walletAddress);
        
        return {
            success: true,
            walletAddress: walletAddress,
            walletType: 'MetaMask'
        };
    } catch (error) {
        console.error('Error connecting to wallet:', error);
        
        // Handle user rejected request error
        if (error.code === 4001) {
            return {
                success: false,
                error: 'User rejected the connection request'
            };
        }
        
        return {
            success: false,
            error: error.message || 'Failed to connect wallet'
        };
    }
}

// Link wallet to user account
async function linkWalletToAccount(walletAddress) {
    try {
        const response = await fetch('/api/user/link-wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            },
            body: JSON.stringify({ wallet_address: walletAddress })
        });
        
        return await response.json();
    } catch (error) {
        console.error('Error linking wallet to account:', error);
        return {
            success: false,
            error: error.message || 'Failed to link wallet to account'
        };
    }
}

// Disconnect wallet from user account
async function disconnectWallet() {
    try {
        const response = await fetch('/api/user/unlink-wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            }
        });
        
        return await response.json();
    } catch (error) {
        console.error('Error disconnecting wallet:', error);
        return {
            success: false,
            error: error.message || 'Failed to disconnect wallet'
        };
    }
}

// Show wallet installation options
function showWalletInstallOptions(container) {
    const optionsDiv = document.createElement('div');
    optionsDiv.className = 'card mt-3';
    optionsDiv.innerHTML = `
        <div class="card-header bg-dark text-white">
            <div class="d-flex justify-content-between align-items-center">
                <h5 class="mb-0">Install a Wallet</h5>
                <button type="button" class="btn-close btn-close-white" id="close-wallet-options"></button>
            </div>
        </div>
        <div class="card-body">
            <p>You need to install a Web3 wallet to connect:</p>
            <div class="list-group">
                <a href="https://metamask.io/download/" target="_blank" class="list-group-item list-group-item-action d-flex align-items-center">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/3/36/MetaMask_Fox.svg" alt="MetaMask" style="width: 30px; margin-right: 10px;">
                    Install MetaMask
                </a>
                <a href="https://www.coinbase.com/wallet" target="_blank" class="list-group-item list-group-item-action d-flex align-items-center">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/1/1a/Coinbase.svg" alt="Coinbase Wallet" style="width: 30px; margin-right: 10px;">
                    Install Coinbase Wallet
                </a>
            </div>
        </div>
    `;
    
    container.appendChild(optionsDiv);
    
    document.getElementById('close-wallet-options').addEventListener('click', function() {
        optionsDiv.remove();
    });
    
    return optionsDiv;
}

// Show loading state for a button
function setButtonLoading(button, text = 'Loading...') {
    button.disabled = true;
    button.setAttribute('data-original-text', button.innerHTML);
    button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${text}`;
}

// Reset button to original state
function resetButton(button) {
    button.disabled = false;
    const originalText = button.getAttribute('data-original-text');
    if (originalText) {
        button.innerHTML = originalText;
    }
}

// Show alert message
function showAlert(containerOrMessage, typeOrMessage, messageOrAutoHide, autoHideParam = true) {
    // Check if the first parameter is a string (meaning it was called from login.html)
    if (typeof containerOrMessage === 'string') {
        // Get the alert container from the page
        const alertContainer = document.getElementById('alertContainer');
        const alertDiv = document.getElementById('alertMessage');
        
        if (alertContainer && alertDiv) {
            // This matches the login.html pattern: showAlert(message, type)
            const message = containerOrMessage;
            const type = typeOrMessage;
            
            // Set the alert type and message
            alertDiv.className = `alert alert-${type}`;
            alertDiv.textContent = message;
            
            // Show the alert container
            alertContainer.style.display = 'block';
            
            // Hide after 5 seconds
            setTimeout(() => {
                alertContainer.style.display = 'none';
            }, 5000);
        } else {
            console.error('Alert container elements not found in the DOM');
        }
    } else {
        // Original functionality: showAlert(container, type, message, autoHide)
        const container = containerOrMessage;
        const type = typeOrMessage;
        const message = messageOrAutoHide;
        const autoHide = autoHideParam;
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} mt-3`;
        alertDiv.textContent = message;
        
        container.appendChild(alertDiv);
        
        if (autoHide) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, 5000);
        }
    }
}

// Export functions
window.YAPWallet = {
    connect: connectWallet,
    link: linkWalletToAccount,
    disconnect: disconnectWallet,
    showInstallOptions: showWalletInstallOptions,
    setButtonLoading: setButtonLoading,
    resetButton: resetButton,
    showAlert: showAlert
}; 