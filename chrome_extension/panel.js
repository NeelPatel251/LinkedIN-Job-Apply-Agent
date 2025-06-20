let activeEventSource = null;

// Restore state when the popup opens
document.addEventListener('DOMContentLoaded', async () => {
    await restoreFormState();
    await restoreLogState();
});

// Save form data as user types
document.getElementById("profileForm").addEventListener('input', debounce(saveFormState, 500));

document.getElementById("continueAgentBtn").addEventListener("click", async () => {
    const logBox = document.getElementById("logOutput");
    logBox.textContent += `\n[${new Date().toLocaleTimeString()}] Sending continue signal to agent...\n`;

    try {
        const response = await fetch("http://localhost:5000/agent/continue-agent", { method: "POST" });
        const result = await response.json();
        logBox.textContent += `[${new Date().toLocaleTimeString()}] ${result.message}\n`;
    } catch (err) {
        logBox.textContent += `[${new Date().toLocaleTimeString()}] Failed to send continue signal: ${err.message}\n`;
    }

    logBox.scrollTop = logBox.scrollHeight;
});

// Save form state to Chrome storage
async function saveFormState() {
    const form = document.getElementById("profileForm");
    const formData = Object.fromEntries(new FormData(form).entries());
    try {
        await chrome.storage.local.set({ formData });
    } catch (error) {
        console.log('Storage not available');
    }
}

// Restore form state
async function restoreFormState() {
    try {
        const result = await chrome.storage.local.get(['formData']);
        if (result.formData) {
            const form = document.getElementById("profileForm");
            Object.entries(result.formData).forEach(([key, value]) => {
                const input = form.querySelector(`[name="${key}"]`);
                if (input && value) input.value = value;
            });
        }
    } catch (error) {
        console.log('Storage not available');
    }
}

// Save logs and agent status
async function saveLogState(logContent, isAgentRunning = false) {
    try {
        await chrome.storage.local.set({
            logContent,
            isAgentRunning,
            lastUpdated: Date.now()
        });
    } catch (error) {
        console.log('Storage error');
    }
}

// Restore log and reconnect state
async function restoreLogState() {
    try {
        const result = await chrome.storage.local.get(['logContent', 'isAgentRunning', 'lastUpdated']);
        const logBox = document.getElementById("logOutput");
        if (result.logContent) {
            logBox.textContent = result.logContent;
            logBox.scrollTop = logBox.scrollHeight;

            const submitBtn = document.querySelector('.submit-btn');

            if (result.isAgentRunning && Date.now() - result.lastUpdated < 5 * 60 * 1000) {
                submitBtn.textContent = 'Reconnect to Agent';
                submitBtn.dataset.mode = 'reconnect';
                document.getElementById("continueAgentBtn").style.display = "block";
            } else {
                submitBtn.textContent = 'Start Agent';
                submitBtn.dataset.mode = 'start';
            }
        }
    } catch (error) {
        console.log('Storage error');
    }
}

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

function reconnectToAgent() {
    if (activeEventSource) return;

    const logBox = document.getElementById("logOutput");
    const submitBtn = document.querySelector('.submit-btn');

    logBox.textContent += `\n[${new Date().toLocaleTimeString()}] Reconnecting to existing agent session...\n`;

    activeEventSource = new EventSource("http://localhost:5000/agent/start-agent");

    submitBtn.classList.add('loading');
    submitBtn.textContent = 'Reconnecting...';
    submitBtn.dataset.mode = 'reconnecting';

    activeEventSource.onopen = async () => {
        logBox.textContent += `[${new Date().toLocaleTimeString()}] Reconnected to agent!\n`;
        logBox.scrollTop = logBox.scrollHeight;
        await saveLogState(logBox.textContent, true);
    };

    activeEventSource.onmessage = async (event) => {
        const timestamp = new Date().toLocaleTimeString();
        logBox.textContent += `[${timestamp}] ${event.data}\n`;
        logBox.scrollTop = logBox.scrollHeight;
        await saveLogState(logBox.textContent, true);

        if (event.data.includes("Please answer") || event.data.includes("manual input")) {
            document.getElementById("continueAgentBtn").style.display = "block";
        }

        if (event.data.includes("completed") || event.data.includes("finished")) {
            submitBtn.classList.remove('loading');
            submitBtn.textContent = 'Start Agent';
            submitBtn.dataset.mode = 'start';
            await saveLogState(logBox.textContent, false);
            activeEventSource.close();
            activeEventSource = null;
        }
    };

    activeEventSource.onerror = async () => {
        logBox.textContent += `[${new Date().toLocaleTimeString()}] Failed to reconnect - agent may have stopped\n`;
        submitBtn.classList.remove('loading');
        submitBtn.textContent = 'Start Agent';
        submitBtn.dataset.mode = 'start';
        await saveLogState(logBox.textContent, false);
        activeEventSource.close();
        activeEventSource = null;
    };
}

document.getElementById("profileForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const formData = Object.fromEntries(new FormData(form).entries());
    const logBox = document.getElementById("logOutput");
    const submitBtn = form.querySelector('.submit-btn');

    if (submitBtn.dataset.mode === 'reconnect') {
        reconnectToAgent();
        return;
    }

    submitBtn.classList.add('loading');
    submitBtn.textContent = 'Starting Agent...';
    submitBtn.dataset.mode = 'starting';

    logBox.textContent = "Initializing AI Job Agent...\n";
    logBox.textContent += "Profile Information:\n";
    for (const [key, value] of Object.entries(formData)) {
        logBox.textContent += `   • ${key.replaceAll('_', ' ')}: ${value}\n`;
    }
    logBox.textContent += "\n";
    await saveLogState(logBox.textContent, false);

    try {
        logBox.textContent += "Sending profile to agent server...\n";
        await saveLogState(logBox.textContent, false);

        await fetch("http://localhost:5000/agent/set-profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(formData)
        });

        logBox.textContent += "Profile saved successfully!\n";
        logBox.textContent += "Connecting to AI agent...\n";
        logBox.scrollTop = logBox.scrollHeight;
        await saveLogState(logBox.textContent, false);

        reconnectToAgent();
    } catch (err) {
        logBox.textContent += `Exception: ${err.message}\n`;
        logBox.textContent += "Check if backend server is running and accessible\n";
        logBox.scrollTop = logBox.scrollHeight;
        await saveLogState(logBox.textContent, false);

        submitBtn.classList.remove('loading');
        submitBtn.textContent = 'Start Agent';
        submitBtn.dataset.mode = 'start';
    }
});
