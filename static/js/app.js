let spendingChart = null;

function switchTab(tabName) {
    document.querySelectorAll('.nav-link').forEach(node => node.classList.remove('active'));
    document.querySelectorAll('.tab-view').forEach(node => node.classList.remove('active'));
    document.getElementById(`nav-${tabName}`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

function showToast(message, success = true) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.style.background = success ? 'rgba(52, 211, 153, 0.12)' : 'rgba(251, 113, 133, 0.12)';
    toast.style.color = success ? '#d1fae5' : '#fecaca';
    toast.classList.add('visible');
    setTimeout(() => toast.classList.remove('visible'), 3000);
}

function setStatusBadge(label, online = true) {
    const badge = document.getElementById('plaid-badge');
    badge.textContent = label;
    badge.className = online ? 'badge badge-online' : 'badge badge-warning';
}

function setNetworkBadge(isOnline) {
    const badge = document.getElementById('network-badge');
    badge.textContent = isOnline ? 'Online' : 'Offline';
    badge.className = isOnline ? 'badge badge-online' : 'badge badge-offline';
}

function createChart(labels, values) {
    const ctx = document.getElementById('spendingChart').getContext('2d');
    if (spendingChart) {
        spendingChart.data.labels = labels;
        spendingChart.data.datasets[0].data = values;
        spendingChart.update();
        return;
    }

    spendingChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Spending',
                    data: values,
                    borderColor: '#d1d5db',
                    backgroundColor: 'rgba(209, 213, 219, 0.18)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#f8fafc',
                    pointBorderColor: '#94a3b8',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: { grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#cbd5e1' } },
                y: { grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#cbd5e1' } },
            },
        },
    });
}

function formatCurrency(value) {
    return `${value >= 0 ? '' : '-'}$${Math.abs(value).toFixed(2)}`;
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function renderIdentity(identity, accounts) {
    const container = document.getElementById('identity-summary');
    container.innerHTML = '';

    if (!identity?.name) {
        container.innerHTML = '<div class="info-message">No linked identity yet. Connect Plaid to see the account holder.</div>';
        return;
    }

    const totalBalance = accounts.reduce((sum, account) => sum + (account.current_balance ?? 0), 0);
    container.innerHTML = `
        <div class="summary-item">
            <strong>${identity.name}</strong>
            <span>${accounts.length} linked account${accounts.length === 1 ? '' : 's'}</span>
            <span>Combined balance: ${formatCurrency(totalBalance)}</span>
        </div>
    `;
}

function renderAccounts(accounts) {
    const container = document.getElementById('account-summary');
    container.innerHTML = '';

    if (!accounts.length) {
        container.innerHTML = '<div class="info-message">No account data cached yet. Connect Plaid to see balances.</div>';
        return;
    }

    accounts.forEach(account => {
        const item = document.createElement('div');
        item.className = 'summary-item';
        item.innerHTML = `
            <strong>${account.name} • ${account.mask || '••••'}</strong>
            <span>${account.type || 'Account'} · ${account.subtype || 'Unknown'}</span>
            <span>${formatCurrency(account.current_balance ?? 0)} available</span>
        `;
        container.appendChild(item);
    });
}

function renderTransactions(transactions) {
    const container = document.getElementById('transaction-list');
    container.innerHTML = '';

    if (!transactions.length) {
        container.innerHTML = '<div class="info-message">No transactions available. Use the refresh button after connecting Plaid.</div>';
        return;
    }

    transactions.forEach(transaction => {
        const card = document.createElement('div');
        card.className = 'transaction-card';
        card.innerHTML = `
            <div>
                <h3>${transaction.name || 'Unknown merchant'}</h3>
                <p>${transaction.category || 'General'} · ${formatDate(transaction.date)}</p>
            </div>
            <div class="transaction-amount">${formatCurrency(transaction.amount)}</div>
        `;
        container.appendChild(card);
    });
}

function renderSpendingChart(transactions) {
    const totalsByDay = {};
    const today = new Date();

    for (let i = 6; i >= 0; i -= 1) {
        const date = new Date(today);
        date.setDate(today.getDate() - i);
        totalsByDay[date.toISOString().slice(0, 10)] = 0;
    }

    transactions.forEach(transaction => {
        if (!transaction.date) return;
        const amount = Math.abs(transaction.amount ?? 0);
        if (totalsByDay[transaction.date] !== undefined) {
            totalsByDay[transaction.date] += amount;
        }
    });

    const labels = Object.keys(totalsByDay).map(label => formatDate(label));
    const values = Object.values(totalsByDay).map(value => parseFloat(value.toFixed(2)));
    createChart(labels, values);
}

function populateSettingsForm(settings) {
    document.getElementById('client_id').value = settings.client_id || '';
    document.getElementById('secret').value = settings.secret || '';
    document.getElementById('env').value = settings.env || 'sandbox';
}

async function saveSettings(event) {
    event.preventDefault();
    const payload = {
        client_id: document.getElementById('client_id').value.trim(),
        secret: document.getElementById('secret').value.trim(),
        env: document.getElementById('env').value,
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (data.status === 'success') {
            const toast = document.getElementById('settings-toast');
            toast.classList.add('visible');
            setTimeout(() => toast.classList.remove('visible'), 3000);
            setStatusBadge('Ready to connect', true);
        } else {
            showToast(data.message || 'Unable to save settings.', false);
        }
    } catch (error) {
        showToast('Unable to save settings. Offline or invalid data.', false);
    }
}

async function testSandboxConnection() {
    const button = document.getElementById('test-sandbox-button');
    button.disabled = true;
    try {
        const response = await fetch('/api/plaid/sandbox-test', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            showToast('Sandbox connection succeeded.');
            await loadAppState();
            return;
        }
        showToast(data.message || 'Sandbox test failed.', false);
    } catch (error) {
        showToast('Sandbox test failed. Check your credentials and network.', false);
    } finally {
        button.disabled = false;
    }
}

async function openPlaidLink() {
    try {
        const response = await fetch('/api/plaid-link-token');
        const result = await response.json();

        if (result.status !== 'success') {
            showToast(result.message || 'Unable to create Plaid link token.', false);
            return;
        }

        const handler = Plaid.create({
            token: result.link_token,
            onSuccess: async (public_token) => {
                await exchangePublicToken(public_token);
                await loadAppState();
                showToast('Bank connection successful.');
            },
            onExit: (err) => {
                if (err) {
                    showToast('Plaid Link exited. Try again if needed.', false);
                }
            },
            onEvent: (eventName, metadata) => {
                if (eventName === 'HANDOFF') {
                    setStatusBadge('Authenticating…', true);
                }
            },
        });

        handler.open();
    } catch (error) {
        showToast('Unable to launch Plaid Link. Check your network or config.', false);
    }
}

async function exchangePublicToken(public_token) {
    const response = await fetch('/api/plaid/exchange-public-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ public_token }),
    });
    const data = await response.json();
    if (data.status !== 'success') {
        throw new Error(data.message || 'Unable to exchange public token.');
    }
}

async function refreshData() {
    try {
        const response = await fetch('/api/refresh-transactions', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            showToast('Transactions refreshed.');
            await loadAppState();
            return;
        }
        showToast(data.message || 'Unable to refresh.', false);
    } catch (error) {
        showToast('Refresh failed. Check your connection.', false);
    }
}

async function loadAppState() {
    try {
        const [settingsResponse, transactionResponse] = await Promise.all([
            fetch('/api/settings'),
            fetch('/api/transactions'),
        ]);

        const settingsData = await settingsResponse.json();
        const transactionsData = await transactionResponse.json();

        if (settingsData.status === 'success') {
            populateSettingsForm(settingsData.settings);
        }

        if (transactionsData.status === 'success') {
            const accounts = transactionsData.accounts || [];
            const transactions = transactionsData.transactions || [];
            const identity = transactionsData.identity || {};
            renderIdentity(identity, accounts);
            renderAccounts(accounts);
            renderTransactions(transactions);
            renderSpendingChart(transactions);
            setStatusBadge(transactionsData.linked ? 'Connected' : 'Ready to connect', transactionsData.linked);
            document.getElementById('connect-button').disabled = false;
        }
    } catch (error) {
        setNetworkBadge(false);
        setStatusBadge('Offline mode', false);
        showToast('Unable to load application state. Working with cached data if available.', false);
    }
}

window.addEventListener('online', () => setNetworkBadge(true));
window.addEventListener('offline', () => setNetworkBadge(false));

window.addEventListener('DOMContentLoaded', () => {
    setNetworkBadge(navigator.onLine);
    loadAppState();
});
