const newTaskInput = document.getElementById('newTaskInput');
if (newTaskInput) {
    newTaskInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            addTask();
        }
    });
}

const addTaskBtn = document.getElementById('addTaskBtn');
if (addTaskBtn) {
    addTaskBtn.addEventListener('click', addTask);
}

async function addTask() {
    const input = document.getElementById('newTaskInput');
    const raw = input.value.trim();
    if (!raw) return;

    const parts = raw.split(';').map(part => part.trim()).filter(Boolean);
    if (parts.length === 0) return;

    const list = document.getElementById('taskList');
    for (const description of parts) {
        const response = await fetch('/api/task/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: SESSION_ID, description: description })
        });

        if (response.ok) {
            const task = await response.json();
            const li = document.createElement('li');
            li.className = 'task-item';
            li.dataset.id = task.id;
            li.innerHTML = `
                <div class="checkbox" onclick="toggleTask('${task.id}')"></div>
                <span class="task-text" contenteditable="true" 
                    onblur="updateTaskDescription('${task.id}', this.innerText)">${task.description}</span>
                <button onclick="deleteTask('${task.id}')" class="btn btn-secondary" 
                    style="padding: 0.2rem 0.5rem; font-size: 0.75rem; margin-left: auto;">✕</button>
            `;
            list.appendChild(li);
        }
    }

    input.value = '';
}

async function toggleTask(taskId) {
    const response = await fetch('/api/task/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
    });

    if (response.ok) {
        const data = await response.json();
        const li = document.querySelector(`.task-item[data-id="${taskId}"]`);
        if (data.is_completed) {
            li.classList.add('completed');
        } else {
            li.classList.remove('completed');
        }
    }
}
function scheduleAutoRefresh() {
    const now = new Date();
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
    const ms = now.getMilliseconds();

    // Calculate minutes until next multiple of 5
    // If we're at 12:04, next is 12:05 (1 min away)
    // If we're at 12:05:01, next is 12:10 (4 min 59 sec away)
    const nextMultipleOf5 = Math.ceil((minutes + (seconds / 60) + (ms / 60000)) / 5) * 5;

    // Handle the case where we are exactly on a multiple of 5 (rare but possible)
    let diffMinutes = nextMultipleOf5 - minutes;
    if (diffMinutes === 0) {
        diffMinutes = 5;
    }

    const timeUntilNext = (diffMinutes * 60 * 1000) - (seconds * 1000) - ms;

    setTimeout(() => {
        window.location.reload();
    }, timeUntilNext);
}

// Call it to start the cycle
scheduleAutoRefresh();
