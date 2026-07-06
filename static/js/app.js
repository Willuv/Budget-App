let spendingChart = null;
let budgetState = { income: 0, categories: [] };
let currentTransactions = []; // Added to power the budget actuals

function switchTab(tabName) {
  document
    .querySelectorAll(".nav-link")
    .forEach((node) => node.classList.remove("active"));
  document
    .querySelectorAll(".tab-view")
    .forEach((node) => node.classList.remove("active"));
  document.getElementById(`nav-${tabName}`).classList.add("active");
  document.getElementById(`tab-${tabName}`).classList.add("active");
}

function showToast(message, success = true) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.style.background = success
    ? "rgba(52, 211, 153, 0.12)"
    : "rgba(251, 113, 133, 0.12)";
  toast.style.color = success ? "#d1fae5" : "#fecaca";
  toast.classList.add("visible");
  setTimeout(() => toast.classList.remove("visible"), 3000);
}

function setStatusBadge(label, online = true) {
  const badge = document.getElementById("plaid-badge");
  badge.textContent = label;
  badge.className = online ? "badge badge-online" : "badge badge-warning";
}

function setNetworkBadge(isOnline) {
  const badge = document.getElementById("network-badge");
  badge.textContent = isOnline ? "Online" : "Offline";
  badge.className = isOnline ? "badge badge-online" : "badge badge-offline";
}

function createChart(labels, values) {
  const ctx = document.getElementById("spendingChart").getContext("2d");
  if (spendingChart) {
    spendingChart.data.labels = labels;
    spendingChart.data.datasets[0].data = values;
    spendingChart.update();
    return;
  }

  spendingChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Spending",
          data: values,
          borderColor: "#d1d5db",
          backgroundColor: "rgba(209, 213, 219, 0.18)",
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: "#f8fafc",
          pointBorderColor: "#94a3b8",
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
        x: {
          grid: { color: "rgba(148,163,184,0.08)" },
          ticks: { color: "#cbd5e1" },
        },
        y: {
          grid: { color: "rgba(148,163,184,0.08)" },
          ticks: { color: "#cbd5e1" },
        },
      },
    },
  });
}

function formatCurrency(value) {
  const numericValue = Number(value ?? 0);
  return `${numericValue >= 0 ? "" : "-"}$${Math.abs(numericValue).toFixed(2)}`;
}

function formatTransactionAmount(value) {
  const numValue = Number(value ?? 0);

  // Because your DB stores Income as positive and Expenses as negative:
  const isIncome = numValue >= 0;
  const sign = isIncome ? "+" : "-";
  const color = isIncome ? "#34d399" : "#f87171"; // Green for income, Red for expense

  return `<span style="color:${color}">${sign}$${Math.abs(numValue).toFixed(2)}</span>`;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function renderIdentity(identity, accounts) {
  const container = document.getElementById("identity-summary");
  container.innerHTML = "";

  if (!identity?.name) {
    container.innerHTML =
      '<div class="info-message">No linked identity yet. Connect Plaid to see the account holder.</div>';
    return;
  }

  const totalBalance = accounts.reduce(
    (sum, account) => sum + (account.current_balance ?? 0),
    0,
  );
  container.innerHTML = `
        <div class="summary-item">
            <strong>${identity.name}</strong>
            <span>${accounts.length} linked account${accounts.length === 1 ? "" : "s"}</span>
            <span>Combined balance: ${formatCurrency(totalBalance)}</span>
        </div>
    `;
}

function renderAccounts(accounts) {
  const container = document.getElementById("account-summary");
  container.innerHTML = "";

  if (!accounts.length) {
    container.innerHTML =
      '<div class="info-message">No account data cached yet. Connect Plaid to see balances.</div>';
    return;
  }

  accounts.forEach((account) => {
    const item = document.createElement("div");
    item.className = "summary-item";
    item.innerHTML = `
            <strong>${account.name} • ${account.mask || "••••"}</strong>
            <span>${account.type || "Account"} · ${account.subtype || "Unknown"}</span>
            <span>${formatCurrency(account.current_balance ?? 0)} available</span>
        `;
    container.appendChild(item);
  });
}

function renderTransactions(transactions) {
  const container = document.getElementById("transaction-list");
  container.innerHTML = "";

  if (!transactions.length) {
    container.innerHTML =
      '<div class="info-message">No transactions available. Use the refresh button after connecting Plaid.</div>';
    return;
  }

  transactions.forEach((transaction) => {
    const card = document.createElement("div");
    card.className = "transaction-card";
    card.innerHTML = `
            <div>
                <h3>${transaction.name || "Unknown merchant"}</h3>
                <p>${transaction.category || "General"} · ${formatDate(transaction.date)}</p>
            </div>
            <div class="transaction-amount">${formatTransactionAmount(transaction.amount)}</div>
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

  transactions.forEach((transaction) => {
    if (!transaction.date) return;
    const val = Number(transaction.amount ?? 0);

    // CHART FIX: Only add to the chart if the value is an expense (negative number)
    if (val < 0) {
      if (totalsByDay[transaction.date] !== undefined) {
        totalsByDay[transaction.date] += Math.abs(val);
      }
    }
  });

  const labels = Object.keys(totalsByDay).map((label) => formatDate(label));
  const values = Object.values(totalsByDay).map((value) =>
    parseFloat(value.toFixed(2)),
  );
  createChart(labels, values);
}

function populateSettingsForm(settings) {
  document.getElementById("client_id").value = settings.client_id || "";
  document.getElementById("secret").value = settings.secret || "";
  document.getElementById("env").value = settings.env || "sandbox";
}

function calculateActuals(transactions) {
  let actualIncome = 0;
  let spentByCategory = {};

  // 1. Create a bucket for every custom category you define
  budgetState.categories.forEach((cat) => {
    spentByCategory[cat.name] = 0;
  });

  transactions.forEach((transaction) => {
    const amount = Number(transaction.amount ?? 0);
    const merchantName = String(transaction.name || "").toLowerCase();
    const plaidCategory = String(transaction.category || "").toLowerCase();

    // 2. Track Income
    if (amount > 0) {
      // Note: If your paycheck uses a unique name, add it to this array
      if (
        ["payroll", "salary", "paycheck", "direct deposit", "deposit"].some(
          (kw) => merchantName.includes(kw),
        )
      ) {
        actualIncome += amount;
      }
    }
    // 3. Track Expenses
    else if (amount < 0) {
      const expenseAmount = Math.abs(amount);

      // Try to match the expense to one of your custom categories
      for (let cat of budgetState.categories) {
        const catName = cat.name.toLowerCase();

        // If your category name (e.g. "Food") is anywhere in the merchant name OR Plaid's category
        if (plaidCategory.includes(catName) || merchantName.includes(catName)) {
          spentByCategory[cat.name] += expenseAmount;
          break; // Stop looking once we find a match so we don't double count
        }
      }
    }
  });

  return { actualIncome, actualSpent: spentByCategory };
}

function renderBudgetEditor() {
  const container = document.getElementById("budget-categories");
  container.innerHTML = "";

  if (!budgetState.categories.length) {
    container.innerHTML =
      '<div class="info-message">Add expense categories to build your monthly plan.</div>';
    return;
  }

  const { actualSpent } = calculateActuals(currentTransactions);

  budgetState.categories.forEach((category, index) => {
    // Now it grabs the exact matched total for your specific category
    const spent = actualSpent[category.name] || 0;
    const progress =
      category.amount > 0 ? Math.min((spent / category.amount) * 100, 100) : 0;

    const row = document.createElement("div");
    row.className = "budget-category-row";
    row.style.marginBottom = "15px";

    row.innerHTML = `
      <div style="display: flex; gap: 10px; margin-bottom: 5px;">
        <input type="text" value="${category.name}" placeholder="Expense category" onchange="updateBudgetCategory(${index}, 'name', this.value)" style="flex: 1;" />
        <input type="number" min="0" step="0.01" value="${category.amount}" placeholder="0.00" onchange="updateBudgetCategory(${index}, 'amount', this.value)" style="width: 100px;" />
        <button type="button" onclick="removeBudgetCategory(${index})">Remove</button>
      </div>
      <div class="category-stats" style="font-size: 0.85em; color: #94a3b8; padding-left: 5px;">
        Spent: $${spent.toFixed(2)} / $${Number(category.amount).toFixed(2)}
        <div style="width: 100%; background: rgba(148,163,184,0.2); height: 6px; border-radius: 3px; margin-top: 4px;">
            <div style="width: ${progress}%; background: ${progress >= 100 ? "#f87171" : "#34d399"}; height: 100%; border-radius: 3px; transition: width 0.3s ease;"></div>
        </div>
      </div>
    `;
    container.appendChild(row);
  });

  renderBudgetSummary();
}

function renderBudgetSummary() {
  const { actualIncome, actualSpent } = calculateActuals(currentTransactions);

  const workingIncome =
    actualIncome > 0 ? actualIncome : Number(budgetState.income || 0);

  const totalPlannedExpenses = budgetState.categories.reduce(
    (sum, category) => sum + Number(category.amount || 0),
    0,
  );

  const totalActualExpenses = Object.values(actualSpent).reduce(
    (sum, val) => sum + val,
    0,
  );
  const remaining = workingIncome - totalActualExpenses;

  const totalElement = document.getElementById("budget-total");
  const remainingElement = document.getElementById("budget-remaining");

  totalElement.innerHTML = `Planned: $${totalPlannedExpenses.toFixed(2)} | Spent: $${totalActualExpenses.toFixed(2)}`;
  remainingElement.textContent = `Left to Spend: $${remaining.toFixed(2)}`;
  remainingElement.style.color = remaining >= 0 ? "#34d399" : "#f87171";
}

function addBudgetCategory() {
  budgetState.categories.push({ name: "New expense", amount: 0 });
  renderBudgetEditor();
}

function updateBudgetCategory(index, field, value) {
  if (!budgetState.categories[index]) {
    return;
  }

  if (field === "name") {
    budgetState.categories[index].name = value;
  } else {
    budgetState.categories[index].amount = Number(value || 0);
  }
  renderBudgetSummary();
}

function removeBudgetCategory(index) {
  budgetState.categories.splice(index, 1);
  renderBudgetEditor();
}

function populateBudgetForm(budget) {
  budgetState = {
    income: Number(budget?.income || 0),
    categories: (budget?.categories || []).map((category) => ({
      name: category.name || "Category",
      amount: Number(category.amount || 0),
    })),
  };

  document.getElementById("budget-income").value = budgetState.income;
  renderBudgetEditor();
}

function inferBudgetFromTransactions(transactions) {
  const payrollIncome = transactions
    .filter((transaction) => {
      const amount = Number(transaction.amount ?? 0);
      const name = String(transaction.name || "").toLowerCase();
      return (
        amount > 0 &&
        ["payroll", "salary", "paycheck", "direct deposit", "deposit"].some(
          (keyword) => name.includes(keyword),
        )
      );
    })
    .reduce(
      (sum, transaction) => sum + Math.abs(Number(transaction.amount ?? 0)),
      0,
    );

  const categoryBuckets = {};
  transactions
    .filter((transaction) => Number(transaction.amount ?? 0) < 0)
    .forEach((transaction) => {
      const category = transaction.category || "Other";
      categoryBuckets[category] =
        (categoryBuckets[category] || 0) +
        Math.abs(Number(transaction.amount ?? 0));
    });

  const categories = Object.entries(categoryBuckets)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 6)
    .map(([name, amount]) => ({ name, amount: Number(amount.toFixed(2)) }));

  return {
    income: Number(payrollIncome.toFixed(2)),
    categories: categories.length
      ? categories
      : [
          { name: "Rent", amount: 0 },
          { name: "Food", amount: 0 },
          { name: "Insurance", amount: 0 },
          { name: "Utilities", amount: 0 },
          { name: "Transportation", amount: 0 },
        ],
  };
}

async function saveBudget() {
  const incomeValue = Number(
    document.getElementById("budget-income").value || 0,
  );
  budgetState.income = incomeValue;
  renderBudgetSummary();

  try {
    const response = await fetch("/api/budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget: budgetState }),
    });
    const data = await response.json();

    if (data.status === "success") {
      populateBudgetForm(data.budget || budgetState);
      showToast("Budget saved.");
    } else {
      showToast(data.message || "Unable to save budget.", false);
    }
  } catch (error) {
    showToast("Unable to save budget right now.", false);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = {
    client_id: document.getElementById("client_id").value.trim(),
    secret: document.getElementById("secret").value.trim(),
    env: document.getElementById("env").value,
  };

  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (data.status === "success") {
      const toast = document.getElementById("settings-toast");
      toast.classList.add("visible");
      setTimeout(() => toast.classList.remove("visible"), 3000);
      setStatusBadge("Ready to connect", true);
    } else {
      showToast(data.message || "Unable to save settings.", false);
    }
  } catch (error) {
    showToast("Unable to save settings. Offline or invalid data.", false);
  }
}

async function testSandboxConnection() {
  const button = document.getElementById("test-sandbox-button");
  button.disabled = true;
  try {
    const response = await fetch("/api/plaid/sandbox-test", { method: "POST" });
    const data = await response.json();
    if (data.status === "success") {
      showToast("Sandbox connection succeeded.");
      await loadAppState();
      return;
    }
    showToast(data.message || "Sandbox test failed.", false);
  } catch (error) {
    showToast(
      "Sandbox test failed. Check your credentials and network.",
      false,
    );
  } finally {
    button.disabled = false;
  }
}

async function openPlaidLink() {
  try {
    const response = await fetch("/api/plaid-link-token");
    const result = await response.json();

    if (result.status !== "success") {
      showToast(result.message || "Unable to create Plaid link token.", false);
      return;
    }

    const handler = Plaid.create({
      token: result.link_token,
      onSuccess: async (public_token) => {
        await exchangePublicToken(public_token);
        await loadAppState();
        showToast("Bank connection successful.");
      },
      onExit: (err) => {
        if (err) {
          showToast("Plaid Link exited. Try again if needed.", false);
        }
      },
      onEvent: (eventName, metadata) => {
        if (eventName === "HANDOFF") {
          setStatusBadge("Authenticating…", true);
        }
      },
    });

    handler.open();
  } catch (error) {
    showToast(
      "Unable to launch Plaid Link. Check your network or config.",
      false,
    );
  }
}

async function exchangePublicToken(public_token) {
  const response = await fetch("/api/plaid/exchange-public-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ public_token }),
  });
  const data = await response.json();
  if (data.status !== "success") {
    throw new Error(data.message || "Unable to exchange public token.");
  }
}

async function refreshData() {
  try {
    const response = await fetch("/api/refresh-transactions", {
      method: "POST",
    });
    const data = await response.json();
    if (data.status === "success") {
      showToast("Transactions refreshed.");
      await loadAppState();
      return;
    }
    showToast(data.message || "Unable to refresh.", false);
  } catch (error) {
    showToast("Refresh failed. Check your connection.", false);
  }
}

async function loadAppState() {
  try {
    const [settingsResponse, transactionResponse, budgetResponse] =
      await Promise.all([
        fetch("/api/settings"),
        fetch("/api/transactions"),
        fetch("/api/budget"),
      ]);

    const settingsData = await settingsResponse.json();
    const transactionsData = await transactionResponse.json();
    const budgetData = await budgetResponse.json();

    if (settingsData.status === "success") {
      populateSettingsForm(settingsData.settings);
    }

    if (transactionsData.status === "success") {
      const txns = transactionsData.transactions || [];
      currentTransactions = txns; // Store globally to drive budget calculations

      if (budgetData.status === "success") {
        const suggestedBudget =
          budgetData.budget &&
          (budgetData.budget.income || budgetData.budget.categories?.length)
            ? budgetData.budget
            : inferBudgetFromTransactions(txns);
        populateBudgetForm(suggestedBudget);
      }

      const accounts = transactionsData.accounts || [];
      const identity = transactionsData.identity || {};
      renderIdentity(identity, accounts);
      renderAccounts(accounts);
      renderTransactions(txns);
      renderSpendingChart(txns);
      setStatusBadge(
        transactionsData.linked ? "Connected" : "Ready to connect",
        transactionsData.linked,
      );
      document.getElementById("connect-button").disabled = false;
    }
  } catch (error) {
    setNetworkBadge(false);
    setStatusBadge("Offline mode", false);
    showToast(
      "Unable to load application state. Working with cached data if available.",
      false,
    );
  }
}

window.addEventListener("online", () => setNetworkBadge(true));
window.addEventListener("offline", () => setNetworkBadge(false));

window.addEventListener("DOMContentLoaded", () => {
  setNetworkBadge(navigator.onLine);
  document
    .getElementById("budget-income")
    .addEventListener("input", (event) => {
      budgetState.income = Number(event.target.value || 0);
      renderBudgetSummary();
    });
  loadAppState();
});
