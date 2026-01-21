// TaskGrid Frontend Configuration
const CONFIG = {
    // API Configuration
    API_BASE_URL: 'http://127.0.0.1:5000',
    
    // Storage Keys
    STORAGE_KEYS: {
        TOKEN: 'taskgrid_token',
        USER: 'taskgrid_user',
        SETUP: 'taskgridSetup'
    },
    
    // API Endpoints
    ENDPOINTS: {
        // Auth
        LOGIN: '/auth/login',
        REGISTER: '/auth/register',
        PROFILE: '/auth/profile',
        
        // Data
        DASHBOARD: '/data/dashboard',
        PROJECTS: '/data/projects',
        TASKS: '/data/tasks',
        WORK_LOGS: '/data/work-logs',
        USERS: '/data/users'
    },
    
    // UI Settings
    TOAST_DURATION: 5000,
    AUTO_REFRESH_INTERVAL: 30000
};

// Export for use in other files
if (typeof window !== 'undefined') {
    window.CONFIG = CONFIG;
}