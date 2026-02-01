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

// Custom Color Palette
const TAG_COLORS = [
    '#EF4444', // Red
    '#F97316', // Orange
    '#F59E0B', // Amber
    '#84CC16', // Lime
    '#10B981', // Emerald
    '#06B6D4', // Cyan
    '#3B82F6', // Blue
    '#6366F1', // Indigo
    '#8B5CF6', // Violet
    '#EC4899'  // Pink
];

function showColorPicker(event, tagId) {
    event.stopPropagation();

    // Close existing pickers
    document.querySelectorAll('.color-picker-popup').forEach(el => el.remove());

    const trigger = event.target;
    const rect = trigger.getBoundingClientRect();

    const popup = document.createElement('div');
    popup.className = 'color-picker-popup';
    popup.style.top = (window.scrollY + rect.bottom + 5) + 'px';
    popup.style.left = (window.scrollX + rect.left) + 'px';

    TAG_COLORS.forEach(color => {
        const swatch = document.createElement('div');
        swatch.className = 'color-swatch';
        swatch.style.backgroundColor = color;
        swatch.onclick = async (e) => {
            e.stopPropagation();
            await updateTagColor(tagId, color);
            popup.remove();
        };
        popup.appendChild(swatch);
    });

    document.body.appendChild(popup);

    // Initial click outside listener
    setTimeout(() => {
        const closer = (e) => {
            if (!popup.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closer);
            }
        };
        document.addEventListener('click', closer);
    }, 0);
}


async function addTask() {
    const input = document.getElementById('newTaskInput');
    const raw = input.value.trim();
    if (!raw) return;

    const parts = raw.split(';').map(part => part.trim()).filter(Boolean);
    if (parts.length === 0) return;

    const list = document.getElementById('taskList');
    for (let description of parts) {
        let tag = null;
        const tagMatch = description.match(/#(\w+)/);
        if (tagMatch) {
            tag = tagMatch[1];
            description = description.replace(tagMatch[0], '').trim();
        }

        const response = await fetch('/api/task/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: SESSION_ID, description: description, tag: tag })
        });

        if (response.ok) {
            const task = await response.json();
            const li = document.createElement('li');
            li.className = 'task-item';
            li.dataset.id = task.id;
            li.innerHTML = `
            <div class="drag-handle" style="cursor: grab; color: var(--text-secondary); margin-right: 0.5rem; display: flex; align-items: center;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/></svg>
            </div>
            <div class="checkbox" onclick="toggleTask('${task.id}')"></div>
            <div style="flex: 1; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                <span class="task-text" contenteditable="true" 
                    onblur="updateTaskDescription('${task.id}', this.innerText)" style="flex: 1;">${task.description}</span>
                <div id="tags-${task.id}" style="display:flex; gap:0.25rem; align-items:center;">
                    ${(task.tags || []).map(t => `
                    <span class="tag-pill" style="color: ${t.color};">
                        <span class="tag-color-dot" style="color: ${t.color};" onclick="showColorPicker(event, '${t.id}')"></span>
                        <span class="tag-text">${t.name}</span>
                        <span class="tag-remove-btn" onclick="removeTag('${task.id}', '${t.name}')">×</span>
                    </span>
                    `).join('')}
                    <button class="btn btn-secondary btn-sm add-tag-btn" onclick="showTagMenu(this, '${task.id}')">
                        <span style="margin-right: 2px;">+</span> Tag
                    </button>
                </div>
            </div>
            <a href="/focus/task/${task.id}" class="btn btn-secondary"
                style="padding: 0.2rem 0.5rem; font-size: 0.75rem; margin-left: auto;">${(typeof i18n !== 'undefined' && i18n.focus) ? i18n.focus : 'Focus'}</a>
            <button onclick="deleteTask('${task.id}')" class="btn btn-secondary" 
                style="padding: 0.2rem 0.5rem; font-size: 0.75rem; margin-left: 0.5rem;">✕</button>
        `;
            list.appendChild(li);
        }
    }

    input.value = '';
}

// Tag Menu Logic - No Caching
async function showTagMenu(btn, taskId) {
    closeTagMenus();

    const menu = document.createElement('div');
    menu.className = 'tag-menu';
    menu.innerHTML = '<div style="padding:0.5rem; text-align:center; color:var(--text-secondary);">Loading...</div>';

    // Position
    const rect = btn.getBoundingClientRect();
    menu.style.top = (window.scrollY + rect.bottom + 5) + 'px';
    menu.style.left = (window.scrollX + rect.left) + 'px';
    document.body.appendChild(menu);

    // Fetch tags fresh every time
    let tags = [];
    try {
        const res = await fetch('/api/tags');
        if (res.ok) {
            tags = await res.json();
        }
    } catch (e) {
        console.error("Failed to load tags", e);
    }

    menu.innerHTML = '';

    // Search Input
    const input = document.createElement('input');
    input.placeholder = "Tag name...";
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const val = input.value.trim();
            if (val) {
                await addTagToTaskRaw(taskId, val);
                closeTagMenus();
            }
        }
    });
    input.addEventListener('input', () => renderTagList(list, tags, input.value, taskId));

    menu.appendChild(input);

    // List Container
    const list = document.createElement('div');
    list.style.maxHeight = '150px';
    list.style.overflowY = 'auto';
    menu.appendChild(list);

    // Initial Render
    renderTagList(list, tags, '', taskId);
    input.focus();

    setTimeout(() => {
        document.addEventListener('click', closeTagMenusOnOutside);
    }, 0);
}

function renderTagList(container, tags, filter, taskId) {
    container.innerHTML = '';
    const filterLower = filter.toLowerCase();
    const matches = tags.filter(t => t.name.toLowerCase().includes(filterLower));

    matches.forEach(tag => {
        const item = document.createElement('div');
        item.className = 'tag-menu-item';
        // Flex container to separate tag info and delete button
        item.style.display = 'flex';
        item.style.justifyContent = 'space-between';

        const info = document.createElement('div');
        info.style.display = 'flex';
        info.style.alignItems = 'center';
        info.innerHTML = `
            <div style="width: 12px; height: 12px; border-radius: 50%; background-color: ${tag.color}; border: 1px solid rgba(0,0,0,0.1); margin-right: 8px;"></div>
            <span>${tag.name}</span>
        `;

        const delBtn = document.createElement('span');
        delBtn.innerHTML = '×'; // or a trash icon
        delBtn.style.cursor = 'pointer';
        delBtn.style.padding = '0 5px';
        delBtn.style.color = 'var(--text-secondary)';
        delBtn.style.fontSize = '1.2em';
        delBtn.title = "Delete tag globally";
        delBtn.onclick = async (e) => {
            e.stopPropagation();
            if (confirm(`Delete tag "${tag.name}" completely? This will remove it from all tasks.`)) {
                await deleteTag(tag.id);
                // Refresh list locally
                const idx = tags.findIndex(t => t.id === tag.id);
                if (idx > -1) tags.splice(idx, 1);
                renderTagList(container, tags, filter, taskId);
            }
        };

        item.appendChild(info);
        item.appendChild(delBtn);

        item.onclick = async () => {
            await addTagToTaskRaw(taskId, tag.name);
            closeTagMenus();
        };
        container.appendChild(item);
    });

    if (matches.length === 0 && filter) {
        const item = document.createElement('div');
        item.className = 'tag-menu-item';
        item.innerText = `Create "${filter}"`;
        item.style.fontStyle = 'italic';
        item.onclick = async () => {
            await addTagToTaskRaw(taskId, filter);
            closeTagMenus();
        };
        container.appendChild(item);
    }
}

function closeTagMenus() {
    document.querySelectorAll('.tag-menu').forEach(el => el.remove());
    document.removeEventListener('click', closeTagMenusOnOutside);
}

function closeTagMenusOnOutside(e) {
    if (!e.target.closest('.tag-menu') && !e.target.closest('.add-tag-btn')) {
        closeTagMenus();
    }
}

async function addTagToTaskRaw(taskId, tagName) {
    const res = await fetch('/api/task/add_tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, tag_name: tagName })
    });
    if (res.ok) window.location.reload();
}

async function updateTagColor(tagId, color) {
    const res = await fetch('/api/tag/update_color', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag_id: tagId, color: color })
    });
    if (res.ok) window.location.reload();
}

async function removeTag(taskId, tagName) {
    if (!confirm(`Remove tag "${tagName}"?`)) return;
    const res = await fetch('/api/task/remove_tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, tag_name: tagName })
    });
    if (res.ok) window.location.reload();
}

async function deleteTag(tagId) {
    const res = await fetch('/api/tag/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag_id: tagId })
    });

    if (!res.ok) {
        const data = await res.json();
        if (data.in_use) {
            alert("Cannot delete tag: it is currently in use by one or more tasks.");
        } else {
            alert("Failed to delete tag");
        }
        return false;
    }

    // Successfully deleted - reload to update UI
    window.location.reload();
    return true;
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
    const nextMultipleOf5 = Math.ceil((minutes + (seconds / 60) + (ms / 60000)) / 5) * 5;

    // Handle the case where we are exactly on a multiple of 5
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
