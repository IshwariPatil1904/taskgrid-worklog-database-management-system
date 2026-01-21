// TaskGrid Utility Functions
class TaskGridUtils {
    // Toast notification system
    static showToast(message, type = 'info', duration = 5000) {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.toast-notification');
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        
        const icon = type === 'success' ? '✅' : 
                    type === 'error' ? '❌' : 
                    type === 'warning' ? '⚠️' : 'ℹ️';
        
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-icon">${icon}</span>
                <span class="toast-message">${message}</span>
            </div>
        `;

        // Add toast styles if not already present
        if (!document.querySelector('#toast-styles')) {
            const styles = document.createElement('style');
            styles.id = 'toast-styles';
            styles.textContent = `
                .toast-notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: rgba(255, 255, 255, 0.95);
                    color: #333;
                    padding: 12px 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    z-index: 10000;
                    transform: translateX(100%);
                    transition: transform 0.3s ease;
                    max-width: 400px;
                    backdrop-filter: blur(10px);
                }
                .toast-notification.show {
                    transform: translateX(0);
                }
                .toast-success {
                    border-left: 4px solid #10b981;
                }
                .toast-error {
                    border-left: 4px solid #ef4444;
                }
                .toast-warning {
                    border-left: 4px solid #f59e0b;
                }
                .toast-info {
                    border-left: 4px solid #3b82f6;
                }
                .toast-content {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .toast-icon {
                    font-size: 16px;
                }
                .toast-message {
                    font-weight: 500;
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Hide and remove toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // Loading state management
    static setLoading(element, isLoading) {
        if (isLoading) {
            element.style.opacity = '0.6';
            element.style.pointerEvents = 'none';
            element.setAttribute('data-loading', 'true');
            element.textContent = element.textContent.replace('→', '⏳');
        } else {
            element.style.opacity = '1';
            element.style.pointerEvents = 'auto';
            element.removeAttribute('data-loading');
            element.textContent = element.textContent.replace('⏳', '→');
        }
    }

    // Validate email format
    static isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // Handle API errors
    static handleApiError(error, context = '') {
        console.error(`API Error ${context}:`, error);
        
        let message = 'An unexpected error occurred';
        
        if (error.message) {
            message = error.message;
        }
        
        // Handle specific error cases
        if (error.message && error.message.includes('Token has expired')) {
            message = 'Your session has expired. Please login again.';
        }
        
        this.showToast(message, 'error');
    }

    // Format date for display
    static formatDate(dateString) {
        if (!dateString) return 'No date';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    // Get today's date in YYYY-MM-DD format
    static getTodayDate() {
        return new Date().toISOString().split('T')[0];
    }

    // Capitalize first letter
    static capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}

// Make utils available globally
if (typeof window !== 'undefined') {
    window.Utils = TaskGridUtils;
}