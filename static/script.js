document.getElementById('newTaskInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        addTask();
    }
});

document.getElementById('addTaskBtn').addEventListener('click', addTask);

async function addTask() {
    const input = document.getElementById('newTaskInput');
    const description = input.value.trim();
    if (!description) return;

    const response = await fetch('/api/task/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: SESSION_ID, description: description })
    });

    if (response.ok) {
        const task = await response.json();
        const list = document.getElementById('taskList');
        const li = document.createElement('li');
        li.className = 'task-item';
        li.dataset.id = task.id;
        li.innerHTML = `
            <div class="checkbox" onclick="toggleTask(${task.id})"></div>
            <span class="task-text">${task.description}</span>
        `;
        list.appendChild(li);
        input.value = '';
    }
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




