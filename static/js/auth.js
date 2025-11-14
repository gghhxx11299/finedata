// Google Sign-In initialization
function initGoogleSignIn() {
    gapi.load('auth2', function() {
        auth2 = gapi.auth2.init({
            client_id: 'YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com',
            cookiepolicy: 'single_host_origin',
            scope: 'profile email'
        });
        
        attachSigninButtons();
    });
}

function attachSigninButtons() {
    const googleAuthButton = document.getElementById('google-signin');
    if (googleAuthButton) {
        auth2.attachClickHandler(googleAuthButton, {},
            function(googleUser) {
                onGoogleSignInSuccess(googleUser);
            }, 
            function(error) {
                console.log('Google Sign-In error:', error);
            });
    }
}

async function onGoogleSignInSuccess(googleUser) {
    const profile = googleUser.getBasicProfile();
    const id_token = googleUser.getAuthResponse().id_token; // ID token for verification
    
    const userData = {
        googleId: profile.getId(),
        name: profile.getName(),
        email: profile.getEmail(),
        imageUrl: profile.getImageUrl(),
        idToken: id_token
    };
    
    try {
        const response = await fetch('/api/auth/google', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Update UI to show signed in state
            updateAuthUI(true, result.user);
            showNotification('Successfully signed in!', 'success');
        } else {
            showNotification('Sign-in failed. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Error signing in:', error);
        showNotification('Error during sign-in. Please try again.', 'error');
    }
}

async function logout() {
    try {
        // Sign out from Google
        if (typeof auth2 !== 'undefined') {
            await auth2.signOut();
        }
        
        // Sign out from our system
        await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'same-origin'
        });
        
        // Update UI
        updateAuthUI(false);
        showNotification('Successfully signed out!', 'info');
    } catch (error) {
        console.error('Error signing out:', error);
        showNotification('Error during sign-out. Please try again.', 'error');
    }
}

function updateAuthUI(isAuthenticated, user = null) {
    const authSection = document.getElementById('auth-section');
    const userMenu = document.getElementById('user-menu');
    const authButtons = document.getElementById('auth-buttons');
    
    if (isAuthenticated && user) {
        if (authSection) authSection.style.display = 'none';
        if (userMenu) {
            userMenu.style.display = 'block';
            document.getElementById('user-name').textContent = user.name;
            document.getElementById('user-email').textContent = user.email;
        }
        if (authButtons) authButtons.style.display = 'none';
        
        // Enable download buttons
        document.querySelectorAll('.dataset-download-btn').forEach(btn => {
            btn.disabled = false;
            btn.title = 'Download dataset';
        });
    } else {
        if (authSection) authSection.style.display = 'block';
        if (userMenu) userMenu.style.display = 'none';
        if (authButtons) authButtons.style.display = 'flex';
        
        // Disable download buttons
        document.querySelectorAll('.dataset-download-btn').forEach(btn => {
            btn.disabled = true;
            btn.title = 'Please sign in to download datasets';
        });
    }
}

async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/check');
        const result = await response.json();
        
        if (result.authenticated) {
            updateAuthUI(true, result.user);
        } else {
            updateAuthUI(false);
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        updateAuthUI(false);
    }
}

async function downloadDataset(datasetName) {
    // Check if user is authenticated
    const response = await fetch('/api/auth/check');
    const result = await response.json();
    
    if (!result.authenticated) {
        showNotification('Please sign in to download datasets', 'info');
        // Optionally redirect to sign in or open sign in modal
        document.getElementById('signin-modal')?.classList.add('show');
        return false;
    }
    
    // Proceed with download
    window.open(`/api/datasets/${datasetName}`, '_blank');
    return true;
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'error' ? '#d32f2f' : type === 'success' ? '#388e3c' : type === 'warning' ? '#ffa000' : '#1976d2'};
        color: white;
        border-radius: 4px;
        z-index: 10000;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: 'Inter', sans-serif;
        animation: fadeInOut 4s forwards;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after animation
    setTimeout(() => {
        notification.remove();
    }, 4000);
}

// Initialize authentication when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication status on page load
    checkAuthStatus();
    
    // Add event listeners for logout
    document.getElementById('logout-btn')?.addEventListener('click', logout);
    
    // Add event listeners for download buttons
    document.querySelectorAll('.dataset-download-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const datasetName = this.dataset.datasetName || this.dataset.name;
            if (datasetName) {
                downloadDataset(datasetName);
            }
        });
    });
});

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translateX(100%); }
        10% { opacity: 1; transform: translateX(0); }
        90% { opacity: 1; transform: translateX(0); }
        100% { opacity: 0; transform: translateX(100%); }
    }
    
    .dataset-download-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
`;
document.head.appendChild(style);