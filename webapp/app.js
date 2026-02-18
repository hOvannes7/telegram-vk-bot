// Telegram WebApp
const tg = window.Telegram.WebApp;

// Ready
tg.ready();
tg.expand();

// Theme colors
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f4f4f5');

// MainButton
const mainButton = tg.MainButton;
mainButton.setText('🚀 Начать копирование');
mainButton.onClick(handleSubmit);

// Form elements
const form = document.getElementById('copyForm');
const groupIdInput = document.getElementById('groupId');
const startDateInput = document.getElementById('startDate');
const endDateInput = document.getElementById('endDate');
const countInput = document.getElementById('count');
const countRange = document.getElementById('countRange');
const targetChatSelect = document.getElementById('targetChat');
const statusDiv = document.getElementById('status');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');

// Saved groups elements
const savedGroupsSection = document.getElementById('savedGroupsSection');
const addGroupForm = document.getElementById('addGroupForm');
const groupsList = document.getElementById('groupsList');
const noGroupsHint = document.getElementById('noGroupsHint');
const newGroupNameInput = document.getElementById('newGroupName');
const newGroupIdInput = document.getElementById('newGroupId');

// Storage key for saved groups
const SAVED_GROUPS_KEY = 'vk_saved_groups';

// Load saved groups
let savedGroups = JSON.parse(localStorage.getItem(SAVED_GROUPS_KEY) || '[]');

// Set default dates
const today = new Date();
const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

endDateInput.value = today.toISOString().split('T')[0];
startDateInput.value = lastWeek.toISOString().split('T')[0];

// Initialize
renderSavedGroups();
setupEventListeners();

// Setup event listeners
function setupEventListeners() {
    // Range slider sync
    countRange.addEventListener('input', (e) => {
        countInput.value = e.target.value;
    });

    countInput.addEventListener('input', (e) => {
        let value = parseInt(e.target.value) || 1;
        value = Math.max(1, Math.min(100, value));
        countRange.value = value;
        countInput.value = value;
    });

    // Haptic feedback
    document.querySelectorAll('input, select, button').forEach(el => {
        el.addEventListener('click', () => {
            tg.HapticFeedback.impactOccurred('light');
        });
    });
}

// Render saved groups
function renderSavedGroups() {
    if (savedGroups.length === 0) {
        groupsList.classList.add('hidden');
        noGroupsHint.classList.remove('hidden');
        return;
    }
    
    groupsList.classList.remove('hidden');
    noGroupsHint.classList.add('hidden');
    
    groupsList.innerHTML = savedGroups.map((group, index) => `
        <div class="group-item" onclick="selectGroup(${index})">
            <div class="group-info">
                <div class="group-name">${escapeHtml(group.name)}</div>
                <div class="group-id">${escapeHtml(group.id)}</div>
            </div>
            <div class="group-actions">
                <button class="btn-delete" onclick="event.stopPropagation(); deleteGroup(${index})">🗑</button>
            </div>
        </div>
    `).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show add group form
function showAddGroupForm() {
    addGroupForm.classList.remove('hidden');
    newGroupNameInput.focus();
}

// Hide add group form
function hideAddGroupForm() {
    addGroupForm.classList.add('hidden');
    newGroupNameInput.value = '';
    newGroupIdInput.value = '';
}

// Save group
function saveGroup() {
    const name = newGroupNameInput.value.trim();
    const id = newGroupIdInput.value.trim();
    
    if (!name || !id) {
        tg.showAlert('Введите название и ID группы');
        return;
    }
    
    savedGroups.push({ name, id });
    localStorage.setItem(SAVED_GROUPS_KEY, JSON.stringify(savedGroups));
    
    renderSavedGroups();
    hideAddGroupForm();
    
    tg.HapticFeedback.notificationOccurred('success');
}

// Select group
function selectGroup(index) {
    const group = savedGroups[index];
    groupIdInput.value = group.id;
    
    tg.HapticFeedback.selectionChanged();
    
    // Scroll to form
    form.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Delete group
function deleteGroup(index) {
    tg.showConfirm('Удалить это сообщество?', (confirmed) => {
        if (confirmed) {
            savedGroups.splice(index, 1);
            localStorage.setItem(SAVED_GROUPS_KEY, JSON.stringify(savedGroups));
            renderSavedGroups();
            tg.HapticFeedback.notificationOccurred('warning');
        }
    });
}

// Form validation
function validateForm() {
    const groupId = groupIdInput.value.trim();
    const startDate = new Date(startDateInput.value);
    const endDate = new Date(endDateInput.value);
    
    if (!groupId) {
        tg.showAlert('Введите название или ID группы VK');
        return false;
    }
    
    if (startDate > endDate) {
        tg.showAlert('Дата начала должна быть раньше даты окончания');
        return false;
    }
    
    const count = parseInt(countInput.value);
    if (isNaN(count) || count < 1 || count > 100) {
        tg.showAlert('Количество постов должно быть от 1 до 100');
        return false;
    }
    
    return true;
}

// Handle submit
function handleSubmit() {
    if (!validateForm()) {
        return;
    }
    
    const data = {
        action: 'copy_posts',
        groupId: groupIdInput.value.trim(),
        startDate: startDateInput.value,
        endDate: endDateInput.value,
        count: parseInt(countInput.value),
        targetChat: targetChatSelect.value,
        userId: tg.initDataUnsafe?.user?.id || null
    };
    
    // Send data to bot
    tg.sendData(JSON.stringify(data));
    
    // Show processing state
    showProcessing();
}

// Show processing status
function showProcessing() {
    statusDiv.classList.remove('hidden');
    statusDiv.classList.add('processing');
    statusDiv.classList.remove('success', 'error');
    
    document.querySelector('.status-icon').textContent = '⏳';
    document.querySelector('.status-text').textContent = 'Копирование постов...';
    progressFill.style.width = '0%';
    progressText.textContent = '0/0';
    
    mainButton.hide();
    
    // Scroll to status
    statusDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Update progress
function updateProgress(current, total) {
    const percent = total > 0 ? (current / total) * 100 : 0;
    progressFill.style.width = `${percent}%`;
    progressText.textContent = `${current}/${total}`;
}

// Show success
function showSuccess(count) {
    statusDiv.classList.remove('processing', 'error');
    statusDiv.classList.add('success');
    
    document.querySelector('.status-icon').textContent = '✅';
    document.querySelector('.status-text').textContent = `Скопировано ${count} постов!`;
    
    mainButton.setText('🚀 Копировать ещё');
    mainButton.show();
    mainButton.onClick(() => {
        statusDiv.classList.add('hidden');
        mainButton.setText('🚀 Начать копирование');
    });
}

// Show error
function showError(message) {
    statusDiv.classList.remove('processing', 'success');
    statusDiv.classList.add('error');
    
    document.querySelector('.status-icon').textContent = '❌';
    document.querySelector('.status-text').textContent = message || 'Ошибка копирования';
    
    mainButton.setText('🚀 Попробовать снова');
    mainButton.show();
}

// Handle messages from bot
window.addEventListener('message', (event) => {
    const data = event.data;
    
    if (typeof data === 'string') {
        try {
            const message = JSON.parse(data);
            
            if (message.type === 'progress') {
                updateProgress(message.current, message.total);
            } else if (message.type === 'success') {
                showSuccess(message.count);
            } else if (message.type === 'error') {
                showError(message.message);
            }
        } catch (e) {
            // Not JSON, ignore
        }
    }
});

console.log('Mini App initialized');
console.log('Saved groups:', savedGroups);
