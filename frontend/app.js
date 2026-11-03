const API = "/api";
let token = localStorage.getItem("token");
let currentFilter = "all";
let isLogin = true;
let editingId = null;

const $ = (id) => document.getElementById(id);

// ---------- Helpers ----------
function showMessage(text, ok = false) {
  const el = $("message");
  el.textContent = text;
  el.className = "message" + (ok ? " ok" : "");
  setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401 && token) {
    logout();
    throw new Error("Session expired");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(Array.isArray(d) ? d[0].msg : d || "Something went wrong");
  }
  return data;
}

// ---------- Auth ----------
function updateView() {
  const loggedIn = !!token;
  $("authView").classList.toggle("hidden", loggedIn);
  $("appView").classList.toggle("hidden", !loggedIn);
  $("userBar").classList.toggle("hidden", !loggedIn);
  if (loggedIn) {
    $("userName").textContent = localStorage.getItem("username") || "";
    loadTasks();
  }
}

function logout() {
  token = null;
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  updateView();
}

$("authSwitch").addEventListener("click", (e) => {
  e.preventDefault();
  isLogin = !isLogin;
  $("authTitle").textContent = isLogin ? "Login" : "Register";
  $("authForm").querySelector("button").textContent = isLogin
    ? "Login"
    : "Register";
  $("authSwitchText").textContent = isLogin
    ? "No account?"
    : "Already have an account?";
  $("authSwitch").textContent = isLogin ? "Register" : "Login";
});

$("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = await api(isLogin ? "/auth/login" : "/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value,
        password: $("password").value,
      }),
    });
    token = data.token;
    localStorage.setItem("token", token);
    localStorage.setItem("username", data.username);
    $("authForm").reset();
    updateView();
  } catch (err) {
    showMessage(err.message);
  }
});

$("logoutBtn").addEventListener("click", logout);

// ---------- Tasks ----------
async function loadTasks() {
  try {
    const tasks = await api(`/tasks?filter=${currentFilter}`);
    renderTasks(tasks);
  } catch (err) {
    showMessage(err.message);
  }
}

function renderTasks(tasks) {
  const list = $("taskList");
  list.innerHTML = "";
  $("empty").classList.toggle("hidden", tasks.length > 0);

  tasks.forEach((t) => {
    const li = document.createElement("li");
    li.className = "task" + (t.completed ? " done" : "");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = t.completed;
    cb.addEventListener("change", () =>
      updateTask(t.id, { completed: cb.checked }),
    );

    const info = document.createElement("div");
    info.className = "info";
    const title = document.createElement("div");
    title.className = "t-title";
    title.textContent = t.title;
    const desc = document.createElement("div");
    desc.className = "t-desc";
    desc.textContent = t.description;
    info.append(title, desc);

    const actions = document.createElement("div");
    actions.className = "actions";
    const edit = document.createElement("button");
    edit.className = "btn ghost";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => openEdit(t));
    const del = document.createElement("button");
    del.className = "btn danger";
    del.textContent = "Delete";
    del.addEventListener("click", () => deleteTask(t.id));
    actions.append(edit, del);

    li.append(cb, info, actions);
    list.appendChild(li);
  });
}

$("taskForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: $("title").value,
        description: $("description").value,
      }),
    });
    $("taskForm").reset();
    loadTasks();
  } catch (err) {
    showMessage(err.message);
  }
});

async function updateTask(id, changes) {
  try {
    await api(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(changes) });
    loadTasks();
  } catch (err) {
    showMessage(err.message);
    loadTasks();
  }
}

async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  try {
    await api(`/tasks/${id}`, { method: "DELETE" });
    loadTasks();
  } catch (err) {
    showMessage(err.message);
  }
}

// ---------- Edit dialog ----------
function openEdit(task) {
  editingId = task.id;
  $("editTitle").value = task.title;
  $("editDescription").value = task.description;
  $("editDialog").showModal();
}

$("editCancel").addEventListener("click", () => $("editDialog").close());

$("editForm").addEventListener("submit", () => {
  updateTask(editingId, {
    title: $("editTitle").value,
    description: $("editDescription").value,
  });
});

// ---------- Filters ----------
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document
      .querySelectorAll(".chip")
      .forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    currentFilter = chip.dataset.filter;
    loadTasks();
  });
});

updateView();
