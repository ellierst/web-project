    const LOAD_BALANCER_URL = 'http://localhost:3000/api';
    const API_URL = 'http://localhost:8000/api';
        
        let token = localStorage.getItem('token');
        let currentTab = 'all';
        let autoRefreshInterval = null;
        let serverStatuses = {};
        let taskCreationCooldown = false;
        const TASK_COOLDOWN_SECONDS = 5;

        if (token) {
            showMainSection();
            loadTasks();
            startAutoRefresh();
        }

        async function register() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const MessageBox = document.getElementById('authMessage');

            MessageBox.textContent = '';
            MessageBox.classList.add('hidden');
            MessageBox.classList.remove('success', 'error');

            if (!username || !password) {
                MessageBox.textContent = 'Заповніть всі поля!';
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
                return;
            }

            try {
                const response = await fetch(`${API_URL}/auth/register/`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });

                if (response.ok) {
                    MessageBox.textContent = 'Реєстрація успішна! Тепер увійдіть.';
                    MessageBox.classList.remove('hidden');
                    MessageBox.classList.add('success');
                    MessageBox.style.background = '#e7f3ff';
                    MessageBox.style.color = '#0c5460';
                } else {
                    const data = await response.json();
                    let messages = [];
                    for (const key in data) {
                        messages.push(`${key}: ${data[key].join(', ')}`);
                    }
                    MessageBox.textContent = messages.join(' | ');
                    MessageBox.classList.remove('hidden');
                    MessageBox.classList.add('error');
                }
            } catch (error) {
                MessageBox.textContent = 'Помилка: ' + error.message;
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
            }
        }

        async function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const MessageBox = document.getElementById('authMessage');

            MessageBox.textContent = '';
            MessageBox.classList.add('hidden');
            MessageBox.classList.remove('success', 'error');

            if (!username || !password) {
                MessageBox.textContent = 'Заповніть всі поля!';
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
                return;
            }

            try {
                const response = await fetch(`${API_URL}/token/`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });

                if (response.ok) {
                    const data = await response.json();
                    token = data.access;
                    localStorage.setItem('token', token);
                    localStorage.setItem('username', username);
                    showMainSection();
                    loadTasks();
                    startAutoRefresh();
                } else {
                    MessageBox.textContent = 'Невірний username або пароль';
                    MessageBox.classList.remove('hidden');
                    MessageBox.classList.add('error');
                }
            } catch (error) {
                MessageBox.textContent = 'Помилка: ' + error.message;
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
            }
        }

        function logout() {
            token = null;
            localStorage.removeItem('token');
            localStorage.removeItem('username');
            stopAutoRefresh();
            document.getElementById('authSection').classList.remove('hidden');
            document.getElementById('mainSection').classList.add('hidden');
        }

        function showMainSection() {
            document.getElementById('authSection').classList.add('hidden');
            document.getElementById('mainSection').classList.remove('hidden');
            document.getElementById('currentUser').textContent = localStorage.getItem('username');
        }

        async function loadServerStatuses() {
            const servers = ['http://127.0.0.1:8001', 'http://127.0.0.1:8002'];
            
            for (const server of servers) {
                try {
                    const response = await fetch(`${server}/api/server-status/`);
                    if (response.ok) {
                        const data = await response.json();
                        serverStatuses[server] = data;
                    }
                } catch (error) {
                    console.log(`Server ${server} unavailable`);
                }
            }
        }

        const DEFAULT_MAX_TASKS_PER_SERVER = 2;
        const DEFAULT_AVERAGE_TASK_TIME = 300;

        async function createTask() {
            const number = parseInt(document.getElementById('fibNumber').value);
            const MessageBox = document.getElementById('taskMessage');

            MessageBox.textContent = '';
            MessageBox.classList.add('hidden');
            MessageBox.classList.remove('success', 'error');

            if (!number || number < 0 || number > 100000) {
                MessageBox.textContent = 'Введіть число від 0 до 100,000';
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
                return;
            }

            if (taskCreationCooldown) {
                MessageBox.textContent = 'Зачекайте перед додаванням наступної задачі!';
                MessageBox.classList.remove('hidden');
                MessageBox.classList.add('error');
                return;
            }

            setTaskCreationCooldown();

            try {
                const response = await fetch(`${LOAD_BALANCER_URL}/tasks/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({number})
                });

                const data = await response.json();

                if (response.status === 202) {
                    document.getElementById('fibNumber').value = '';
                    loadTasks();
                } else if (response.ok || response.status === 201) {
                    document.getElementById('fibNumber').value = '';
                    loadTasks();
                } else {
                    MessageBox.textContent = 'Помилка: ' + JSON.stringify(data);
                    MessageBox.classList.remove('hidden', 'success');
                    MessageBox.classList.add('error');
                }
            } catch (error) {
                MessageBox.textContent = 'Помилка: ' + error.message;
                MessageBox.classList.remove('hidden', 'success');
                MessageBox.classList.add('error');
            }
        }

        function setTaskCreationCooldown() {
            taskCreationCooldown = true;
            const btn = document.getElementById('createTaskBtn');
            const timer = document.getElementById('taskCooldownTimer');
            const timeDisplay = document.getElementById('cooldownTime');

            btn.disabled = true;
            timer.style.display = 'block';

            let secondsLeft = TASK_COOLDOWN_SECONDS;

            const cooldownInterval = setInterval(() => {
                secondsLeft--;
                timeDisplay.textContent = secondsLeft;

                if (secondsLeft <= 0) {
                    clearInterval(cooldownInterval);
                    taskCreationCooldown = false;
                    btn.disabled = false;
                    timer.style.display = 'none';
                }
            }, 1000);
        }

        async function loadTasks() {
            let url = `${API_URL}/tasks/`;
            
            if (currentTab === 'active') {
                url = `${API_URL}/tasks/active/`;
            } else if (currentTab === 'history') {
                url = `${API_URL}/tasks/history/`;
            }

            try {
                await loadServerStatuses();
                
                const response = await fetch(url, {
                    headers: {'Authorization': `Bearer ${token}`}
                });

                if (response.ok) {
                    const tasks = await response.json();
                    displayTasks(tasks);
                    await updateQueueStatusBanner();
                } else if (response.status === 401) {
                    logout();
                }
            } catch (error) {
                console.error('Error loading tasks:', error);
            }
        }

        async function updateQueueStatusBanner() {
            try {
                const response = await fetch(`${LOAD_BALANCER_URL}/queue-status/`); 
                if (response.ok) {
                    const data = await response.json();
                    const count = data.queue_length;
                    const estimatedTime = data.estimated_wait_time;
                    
                    document.getElementById('queueCount').textContent = count;
                    
                    const bannerTextElement = document.getElementById('queueBannerText');
                    const bannerTimeElement = document.getElementById('queueBannerTime');
                    
                    if (count > 0) {
                        bannerTextElement.innerHTML = `Задач в черзі:`;
                        bannerTimeElement.textContent = `Приблизно ${estimatedTime}`;
                        bannerTimeElement.style.display = 'block';
                        document.getElementById('queueBanner').style.display = 'flex';
                    } else {
                        document.getElementById('queueBanner').style.display = 'none';
                        bannerTimeElement.style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Error fetching queue status:', error);
            }
        }

        function displayTasks(tasks) {
            const container = document.getElementById('tasksList');

            if (tasks.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: #999; padding: 40px;">Задач немає</p>';
                return;
            }

            container.innerHTML = tasks.map(task => {
                let status = task.status;
                const queuePosition = task.queue_position;

                const inLocalQueue = !!queuePosition && status !== 'in_progress' && status !== 'completed' && status !== 'failed' && status !== 'cancelled';
                
                const displayStatus = inLocalQueue ? 'awaiting_dispatch' : status;
                const statusClass = displayStatus;

                let estimatedTime = task.estimated_wait_time;
                if ((!estimatedTime || estimatedTime === 'undefined') && queuePosition) {
                    const numServers = Object.keys(serverStatuses).length || 2;
                    const reportedMax = Object.values(serverStatuses).map(s => s.max_tasks || DEFAULT_MAX_TASKS_PER_SERVER);
                    const maxPerServer = reportedMax.length ? Math.max(...reportedMax) : DEFAULT_MAX_TASKS_PER_SERVER;
                    const avgTime = DEFAULT_AVERAGE_TASK_TIME;

                    const estimatedSeconds = (queuePosition / (numServers * maxPerServer)) * avgTime;
                    if (estimatedSeconds < 60) {
                        estimatedTime = `${Math.round(estimatedSeconds)} секунд`;
                    } else if (estimatedSeconds < 3600) {
                        estimatedTime = `${Math.round(estimatedSeconds / 60)} хвилин`;
                    } else {
                        const hours = Math.floor(estimatedSeconds / 3600);
                        const minutes = Math.floor((estimatedSeconds % 3600) / 60);
                        estimatedTime = `${hours} год ${minutes} хв`;
                    }
                }
                
                return `
                <div class="task-card ${statusClass}">
                    <div class="task-header">
                        <div>
                            <span class="task-title">Task #${task.id} - Fibonacci(${task.number})</span>
                            ${task.server_url ? `<span class="server-info">🔡 ${task.server_url}</span>` : ''}
                        </div>
                        <div>
                            <span class="status-badge status-${statusClass}">${getStatusText(displayStatus)}</span>
                            ${(displayStatus === 'awaiting_dispatch' || displayStatus === 'in_progress') ? 
                                `<button class="btn-danger" onclick="cancelTask(${task.id})"> Скасувати</button>` : ''}
                        </div>
                    </div>

                    ${(displayStatus === 'awaiting_dispatch') && queuePosition ? `
                        <div class="queue-info">
                            <strong>Черга</strong>
                            <div class="queue-details">
                                <div class="queue-item">
                                    <div class="queue-item-label">Позиція в черзі:</div>
                                    <div class="queue-item-value">${queuePosition}</div>
                                </div>
                                <div class="queue-item">
                                    <div class="queue-item-label">Очікуваний час:</div>
                                    <div class="queue-item-value">${estimatedTime}</div>
                                </div>
                            </div>
                        </div>
                    ` : ''}

                    ${(displayStatus === 'in_progress') ? `
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress}%">
                                ${task.progress}%
                            </div>
                        </div>
                    ` : ''}

                    ${task.result ? `
                        <div class="result-box">
                            <strong> Результат:</strong><br>
                            ${task.result}
                        </div>
                    ` : ''}

                    ${task.error_message ? `
                        <div class="error-message">
                            <strong> Помилка:</strong><br>
                            ${task.error_message}
                        </div>
                    ` : ''}

                    <div class="task-info">
                          Створено: ${new Date(task.created_at).toLocaleString('uk-UA')}<br>
                        ${task.completed_at ? `Завершено: ${new Date(task.completed_at).toLocaleString('uk-UA')}` : ''}
                    </div>
                </div>
            `}).join('');
        }

        async function cancelTask(id) {
            if (!confirm('Скасувати задачу?')) return;

            try {
                const response = await fetch(`${API_URL}/tasks/${id}/cancel/`, {
                    method: 'POST',
                    headers: {'Authorization': `Bearer ${token}`}
                });

                if (response.ok) {
                    alert('Задача скасована');
                    loadTasks();
                }
            } catch (error) {
                alert('Помилка: ' + error.message);
            }
        }

        function showTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            loadTasks();
        }

        function getStatusText(status) {
            const statuses = {
                'awaiting_dispatch': 'Очікує на відправку',
                'in_progress': 'Виконується',
                'completed': 'Завершено',
                'failed': 'Помилка',
                'cancelled': 'Скасовано'
            };
            return statuses[status] || ' ';
        }

        function startAutoRefresh() {
            autoRefreshInterval = setInterval(loadTasks, 3000); 
        }

        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
        }