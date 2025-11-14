#!/usr/bin/env python3
"""
Setup script to add Google authentication to all HTML files
and ensure proper structure for the website.
"""

import os
import re
from pathlib import Path

def add_google_auth_to_html(file_path, is_main_nav=False):
    """Add Google authentication functionality to an HTML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add auth section to navigation - find the mobile menu button and add auth before it
    if '<button class="mobile-menu-btn">' in content:
        # Add auth UI elements in the nav
        nav_insert_pattern = r'(<div class="container">\s*<nav>.*?class="nav-links".*?>)'
        if is_main_nav:
            auth_ui_html = '''
        <div id="auth-buttons" style="display: flex; align-items: center; gap: 1rem;">
            <div id="auth-section" style="display: none;">
                <button id="google-signin" class="btn" style="background: #DB4437; display: flex; align-items: center; gap: 8px;">
                    <i class="fab fa-google"></i> Sign in
                </button>
            </div>
            <div id="user-menu" style="display: none; display: flex; align-items: center; gap: 1rem;">
                <span>Welcome, <span id="user-name"></span>!</span>
                <span style="font-size: 0.9em; color: var(--text-muted);" id="user-email"></span>
                <button id="logout-btn" class="btn" style="background: var(--accent);">Logout</button>
            </div>
        </div>'''
        else:
            auth_ui_html = '''
        <div id="auth-buttons" style="display: flex; align-items: center; gap: 1rem;">
            <div id="auth-section" style="display: none;">
                <button id="google-signin" class="export-btn" style="background: #DB4437; display: flex; align-items: center; gap: 8px; max-width: fit-content;">
                    <i class="fab fa-google"></i> Sign in
                </button>
            </div>
            <div id="user-menu" style="display: none; display: flex; align-items: center; gap: 1rem;">
                <span id="user-name" style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;"></span>
                <button id="logout-btn" class="export-btn" style="background: var(--accent);">Logout</button>
            </div>
        </div>'''
        
        content = re.sub(r'(<button class="mobile-menu-btn">)', auth_ui_html + r'\n\1', content, count=1)
    
    # Add Google Sign-In script to the end of the file if it's not already there
    if 'https://apis.google.com/js/platform.js' not in content:
        # Find the closing </body></html>
        if '</body>' in content and '</html>' in content:
            # Insert Google Sign-In and auth script before </body>
            auth_script = '''
    <!-- Google Sign-In -->
    <script src="https://apis.google.com/js/platform.js" async defer></script>
    <script>
        // Google Sign-In initialization
        function initGoogleSignIn() {
            if (typeof gapi !== 'undefined') {
                gapi.load(\'auth2\', function() {
                    gapi.auth2.init({
                        client_id: \'YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com\',
                        cookiepolicy: \'single_host_origin\',
                        scope: \'profile email\'
                    }).then(function(auth) {
                        // Check auth status on page load
                        checkAuthStatus();
                        
                        // Attach sign-in handlers
                        attachSigninHandlers();
                    });
                });
            }
        }

        function attachSigninHandlers() {
            const googleAuthButton = document.getElementById(\'google-signin\');
            if (googleAuthButton) {
                googleAuthButton.addEventListener(\'click\', function() {
                    const auth2 = gapi.auth2.getAuthInstance();
                    auth2.signIn().then(function(googleUser) {
                        onGoogleSignInSuccess(googleUser);
                    }).catch(function(error) {
                        console.log(\'Google Sign-In error:\', error);
                    });
                });
            }
            
            // Logout handler
            document.getElementById(\'logout-btn\')?.addEventListener(\'click\', function() {
                const auth2 = gapi.auth2.getAuthInstance();
                auth2.signOut().then(function() {
                    // Clear user session on server
                    fetch(\'/api/auth/logout\', {
                        method: \'POST\',
                        credentials: \'same-origin\'
                    }).then(() => {
                        // Update UI
                        updateAuthUI(false);
                        showNotification(\'Successfully signed out!\', \'success\');
                    });
                });
            });
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
                const response = await fetch(\'/api/auth/google\', {
                    method: \'POST\',
                    headers: {
                        \'Content-Type\': \'application/json\',
                    },
                    body: JSON.stringify(userData),
                    credentials: \'same-origin\'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Update UI to show signed in state
                    updateAuthUI(true, result.user);
                    showNotification(\'Successfully signed in!\', \'success\');
                } else {
                    showNotification(\'Sign-in failed. Please try again.\', \'error\');
                }
            } catch (error) {
                console.error(\'Error signing in:\', error);
                showNotification(\'Error during sign-in. Please try again.\', \'error\');
            }
        }

        function updateAuthUI(isAuthenticated, user = null) {
            const authSection = document.getElementById(\'auth-section\');
            const userMenu = document.getElementById(\'user-menu\');
            
            if (isAuthenticated && user) {
                if (authSection) authSection.style.display = \'none\';
                if (userMenu) {
                    userMenu.style.display = \'flex\';
                    document.getElementById(\'user-name\')?.textContent = user.name || \'User\';
                    document.getElementById(\'user-email\')?.textContent = user.email || \'\';
                }
            } else {
                if (authSection) authSection.style.display = \'flex\';
                if (userMenu) userMenu.style.display = \'none\';
            }
            
            // Update download/export buttons
            const buttons = document.querySelectorAll(\'.dataset-download-btn, .export-btn, button[onclick*="export"], [data-dataset]\');
            buttons.forEach(btn => {
                if (isAuthenticated) {
                    btn.title = btn.title?.replace(\'Please sign in\', \'Available\') || \'Download/Export available\';
                } else {
                    if (!btn.title?.includes(\'sign in\')) {
                        btn.title = \'Please sign in to download/export data\';
                    }
                }
            });
        }

        async function checkAuthStatus() {
            try {
                const response = await fetch(\'/api/auth/check\', {
                    credentials: \'same-origin\'
                });
                const result = await response.json();
                
                if (result.authenticated) {
                    updateAuthUI(true, result.user);
                } else {
                    updateAuthUI(false);
                }
            } catch (error) {
                console.error(\'Error checking auth status:\', error);
                updateAuthUI(false);
            }
        }

        function showNotification(message, type = \'info\') {
            // Create notification element
            const notification = document.createElement(\'div\');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                background: ${type === \'error\' ? \'#d32f2f\' : type === \'success\' ? \'#388e3c\' : type === \'warning\' ? \'#ffa000\' : \'#1976d2\'};
                color: white;
                border-radius: 4px;
                z-index: 10000;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                font-family: \'Inter\', sans-serif;
                animation: fadeInOut 4s forwards;
            `;
            
            document.body.appendChild(notification);
            
            // Remove after animation
            setTimeout(() => {
                notification.remove();
            }, 4000);
        }
        
        // Initialize authentication when DOM is loaded
        document.addEventListener(\'DOMContentLoaded\', function() {
            // Initialize Google Sign-In
            initGoogleSignIn();
            
            // Add event listeners for download buttons
            document.querySelectorAll(\'.dataset-download-btn, [data-dataset], button[onclick*="export"]\').forEach(btn => {
                btn.addEventListener(\'click\', async function(e) {
                    const isAuthenticated = await checkIfAuthenticated();
                    if (!isAuthenticated) {
                        e.preventDefault();
                        showNotification(\'Please sign in to download datasets\', \'info\');
                        return false;
                    }
                });
            });
        });
        
        async function checkIfAuthenticated() {
            try {
                const response = await fetch(\'/api/auth/check\', {
                    credentials: \'same-origin\'
                });
                const result = await response.json();
                return result.authenticated;
            } catch (error) {
                return false;
            }
        }

        // Add CSS for notifications
        const style = document.createElement(\'style\');
        style.textContent = `
            @keyframes fadeInOut {
                0% { opacity: 0; transform: translateX(100%); }
                10% { opacity: 1; transform: translateX(0); }
                90% { opacity: 1; transform: translateX(0); }
                100% { opacity: 0; transform: translateX(100%); }
            }
            
            .dataset-download-btn:disabled, .export-btn[disabled] {
                opacity: 0.5;
                cursor: not-allowed;
            }
        `;
        document.head.appendChild(style);
    </script>'''
            content = content.replace('</body>', auth_script + '\n</body>')
    
    # Write back the updated content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    """Main function to set up authentication in all HTML files."""
    html_dir = Path('.')
    
    # List of HTML files to modify
    html_files = [
        'index.html',
        'economic.html',
        'demographic.html',
        'agricultural.html',
        'weather.html',
        'insights.html',
        'exchange.html',
        'news.html',
        'support.html',
        'donate.html',
        'pdf.html'
    ]
    
    for html_file in html_files:
        file_path = html_dir / html_file
        if file_path.exists():
            print(f"Updating {html_file}...")
            is_main_nav = html_file in ['index.html']  # Main nav on home page
            add_google_auth_to_html(str(file_path), is_main_nav=is_main_nav)
        else:
            print(f"Warning: {html_file} not found")
    
    print("Auth setup completed!")

if __name__ == "__main__":
    main()