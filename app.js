const views = {
  loading: document.querySelector("#loading-view"),
  account: document.querySelector("#account-view"),
  bind: document.querySelector("#bind-view"),
  dashboard: document.querySelector("#dashboard-view"),
  editor: document.querySelector("#editor-view"),
  public: document.querySelector("#public-view"),
};

const authScopes = {
  account: {
    registerTab: document.querySelector("#account-register-tab"),
    loginTab: document.querySelector("#account-login-tab"),
    registerForm: document.querySelector("#account-register-form"),
    loginForm: document.querySelector("#account-login-form"),
    status: "#account-auth-status",
  },
  bind: {
    registerTab: document.querySelector("#bind-register-tab"),
    loginTab: document.querySelector("#bind-login-tab"),
    registerForm: document.querySelector("#bind-register-form"),
    loginForm: document.querySelector("#bind-login-form"),
    status: "#bind-auth-status",
  },
};

const profileForm = document.querySelector("#profile-form");
const deviceList = document.querySelector("#device-list");
const dashboardEmpty = document.querySelector("#dashboard-empty");
const wechatDialog = document.querySelector("#wechat-dialog");
const fallbackAvatar =
  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=520&q=80";
const DEFAULT_TOKEN = "123";

const SOCIAL_PLATFORM_META = [
  { key: "wechat", label: "微信 / WeChat", subtitle: "好友码已上传", accent: "wechat", short: "W" },
  { key: "douyin", label: "抖音 / Douyin", subtitle: "点击直达主页", accent: "douyin", short: "D" },
  { key: "instagram", label: "Instagram", subtitle: "即将支持", accent: "instagram", short: "IG" },
  { key: "xiaohongshu", label: "小红书 / Xiaohongshu", subtitle: "即将支持", accent: "xiaohongshu", short: "R" },
  { key: "x", label: "Twitter / X", subtitle: "即将支持", accent: "x", short: "X" },
  { key: "youtube", label: "YouTube", subtitle: "即将支持", accent: "youtube", short: "YT" },
];

const state = {
  token: tokenFromPath(),
  selectedDevice: deviceTokenFromQuery(),
  me: null,
  publicProfile: null,
};

show("loading");
wireAuthScope("account");
wireAuthScope("bind");

document.querySelector("#logout-button").addEventListener("click", logout);
document.querySelector("#close-wechat").addEventListener("click", () => wechatDialog.close());
document.querySelector("#copy-wechat").addEventListener("click", () => copyWechat(state.publicProfile));
document.querySelector("#dialog-copy-wechat").addEventListener("click", () => copyWechat(state.publicProfile));
document.querySelector("#public-wechat").addEventListener("click", () => openWechat(state.publicProfile));
document.querySelector("#copy-public-url").addEventListener("click", copyPublicUrl);
profileForm.addEventListener("submit", saveProfile);
profileForm.elements.namedItem("avatarFile").addEventListener("change", loadAvatarFile);
profileForm.elements.namedItem("wechatQrFile").addEventListener("change", loadQrFile);

boot();

function wireAuthScope(scope) {
  const { registerTab, loginTab, registerForm, loginForm, status } = authScopes[scope];
  registerTab.addEventListener("click", () => setAuthMode(scope, "register"));
  loginTab.addEventListener("click", () => setAuthMode(scope, "login"));

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await submitRegister(registerForm, scope === "bind" ? state.token : "", status);
    if (!result.ok) return;
    state.me = result.me;
    updateSessionUi();
    if (scope === "bind") {
      const targetToken = result.me.necklaceToken || state.token || DEFAULT_TOKEN;
      window.location.href = `/account?device=${encodeURIComponent(targetToken)}`;
    } else {
      history.replaceState({}, "", "/account");
      renderDashboard();
      show("dashboard");
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await submitLogin(loginForm, scope === "bind" ? state.token : "", status);
    if (!result.ok) return;
    state.me = result.me;
    updateSessionUi();
    if (scope === "bind") {
      const targetToken = result.me.necklaceToken || state.token || DEFAULT_TOKEN;
      window.location.href = `/account?device=${encodeURIComponent(targetToken)}`;
    } else {
      const deviceToken = selectedDeviceToken();
      if (deviceToken && ownsDevice(deviceToken)) {
        state.selectedDevice = deviceToken;
        history.replaceState({}, "", `/account?device=${encodeURIComponent(deviceToken)}`);
        hydrateEditor(profileForSelectedDevice());
        show("editor");
        return;
      }
      history.replaceState({}, "", "/account");
      renderDashboard();
      show("dashboard");
    }
  });
}

async function boot() {
  show("loading");
  const meResult = await api("/api/me");
  state.me = meResult.me || null;
  updateSessionUi();

  if (state.token) {
    await loadTap(state.token);
    return;
  }

  const slug = profileSlugFromPath();
  if (slug) {
    await loadPublicProfile(slug);
    return;
  }

  if (window.location.pathname === "/" || window.location.pathname.startsWith("/account")) {
    if (!state.me) {
      history.replaceState({}, "", "/account");
      setAuthMode("account", "register");
      show("account");
      return;
    }

    const deviceToken = selectedDeviceToken();
    if (deviceToken && ownsDevice(deviceToken)) {
      state.selectedDevice = deviceToken;
      history.replaceState({}, "", `/account?device=${encodeURIComponent(deviceToken)}`);
      hydrateEditor(profileForSelectedDevice());
      show("editor");
      return;
    }

    history.replaceState({}, "", "/account");
    renderDashboard();
    show("dashboard");
    return;
  }

  history.replaceState({}, "", "/account");
  setAuthMode("account", "register");
  show("account");
}

async function loadTap(token) {
  document.querySelector("#necklace-token").textContent = token;
  document.querySelector("#bind-token-copy").textContent = token;
  document.querySelector("#necklace-path").textContent = `/tap/${token}`;

  const result = await api(`/api/tap/${encodeURIComponent(token)}`);
  if (!result.ok) {
    history.replaceState({}, "", "/account");
    setAuthMode("account", "register");
    show("account");
    return;
  }

  state.me = result.me || state.me;
  updateSessionUi();

  if (result.bound && result.profile) {
    state.publicProfile = result.profile;
    renderPublic(result.profile, token);
    show("public");
    return;
  }

  setAuthMode("bind", state.me ? "login" : "register");
  setStatus(
    "#bind-auth-status",
    state.me ? "你已经登录，提交后会把这条项链认领到当前账号。" : "先注册或登录，再认领这条项链。"
  );
  show("bind");
}

async function loadPublicProfile(slug) {
  const result = await api(`/api/profile/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    history.replaceState({}, "", "/account");
    setAuthMode("account", "register");
    show("account");
    return;
  }
  state.publicProfile = result.profile;
  renderPublic(result.profile, "");
  show("public");
}

function show(name) {
  Object.entries(views).forEach(([key, view]) => {
    if (!view) return;
    view.hidden = key !== name;
  });
  document.body.dataset.ready = name === "loading" ? "0" : "1";
  document.body.dataset.view = name;
  if (name === "editor" && profileForSelectedDevice()) {
    hydrateEditor(profileForSelectedDevice());
  }
  if (name === "dashboard") {
    renderDashboard();
  }
}

function setAuthMode(scope, mode) {
  const scoped = authScopes[scope];
  const registerMode = mode === "register";
  scoped.registerTab.classList.toggle("is-active", registerMode);
  scoped.loginTab.classList.toggle("is-active", !registerMode);
  scoped.registerForm.hidden = !registerMode;
  scoped.loginForm.hidden = registerMode;
  setStatus(scoped.status, "");
}

function renderDashboard() {
  const me = state.me;
  if (!me) return;

  document.querySelector("#dashboard-email").textContent = me.email;
  const devices = me.devices || [];
  document.querySelector("#dashboard-count").textContent = `${devices.length} 台设备`;
  deviceList.replaceChildren();
  dashboardEmpty.hidden = devices.length > 0;

  devices.forEach((device) => {
    const profile = device.profile || {};
    const card = document.createElement("article");
    card.className = "device-card";

    const avatar = document.createElement("img");
    avatar.className = "device-avatar";
    avatar.alt = "设备头像";
    avatar.src = profile.avatar || fallbackAvatar;
    avatar.onerror = () => {
      avatar.src = fallbackAvatar;
    };

    const meta = document.createElement("div");
    meta.className = "device-meta";

    const title = document.createElement("h2");
    title.textContent = profile.name || "未命名设备主页";

    const token = document.createElement("p");
    token.className = "device-token";
    token.textContent = `/tap/${device.token}`;

    const status = document.createElement("span");
    status.className = `device-status ${device.bound ? "is-bound" : "is-empty"}`;
    status.textContent = device.bound ? "已绑定" : "未绑定";

    const actions = document.createElement("div");
    actions.className = "device-actions";

    const editButton = document.createElement("button");
    editButton.className = "primary-button";
    editButton.type = "button";
    editButton.textContent = "编辑这台设备";
    editButton.addEventListener("click", () => openDeviceEditor(device.token));

    const viewLink = document.createElement("a");
    viewLink.className = "quiet-link";
    viewLink.href = `/tap/${device.token}`;
    viewLink.textContent = "查看公开页";

    actions.append(editButton, viewLink);
    meta.append(token, title, status, actions);
    card.append(avatar, meta);
    deviceList.append(card);
  });
}

function openDeviceEditor(token) {
  state.selectedDevice = token;
  history.pushState({}, "", `/account?device=${encodeURIComponent(token)}`);
  hydrateEditor(profileForSelectedDevice());
  show("editor");
}

function profileForSelectedDevice() {
  if (!state.me) return null;
  const token = state.selectedDevice || state.me.necklaceToken;
  const device = (state.me.devices || []).find((item) => item.token === token) || (state.me.devices || [])[0];
  return device?.profile || state.me.profile || null;
}

function ownsDevice(token) {
  return Boolean((state.me?.devices || []).find((item) => item.token === token));
}

function selectedDeviceToken() {
  const params = new URLSearchParams(window.location.search);
  return params.get("device") || "";
}

function hydrateEditor(profile) {
  if (!profile) return;
  profileForm.elements.name.value = profile.name || "";
  profileForm.elements.bio.value = profile.bio || "";
  profileForm.elements.tags.value = (profile.tags || []).join(", ");
  profileForm.elements.wechat.value = profile.wechat || "";
  profileForm.elements.wechatQr.value = profile.wechatQr || "";
  profileForm.elements.douyin.value = profile.douyin || "";
  updateAvatarPreview(profile.avatar || "");

  const token = state.selectedDevice || state.me?.necklaceToken || state.token || DEFAULT_TOKEN;
  const publicUrl = `${window.location.origin}/tap/${token}`;
  document.querySelector("#public-profile-link").href = publicUrl;
  document.querySelector("#back-to-dashboard").href = "/account";
  document.querySelector("#bound-tap-link").href = `/tap/${token}`;
  document.querySelector("#editor-token").textContent = token;
  document.querySelector("#editor-token-path").textContent = `/tap/${token}`;
  document.querySelector("#summary-token").textContent = token;
  document.querySelector("#summary-token-copy").textContent = token;
}

async function saveProfile(event) {
  event.preventDefault();
  const result = await api("/api/profile", {
    method: "PUT",
    body: readProfileForm(),
  });
  if (!result.ok) return setStatus("#editor-status", result.error);
  state.me = result.me;
  updateSessionUi();
  hydrateEditor(result.me.profile);
  renderDashboard();
  setStatus("#editor-status", "设备主页已保存。再碰一次，就会看到最新内容。");
}

function readProfileForm() {
  return {
    token: state.selectedDevice || state.me?.necklaceToken || state.token || DEFAULT_TOKEN,
    name: profileForm.elements.name.value.trim(),
    avatar: profileForm.dataset.avatar || "",
    bio: profileForm.elements.bio.value.trim(),
    tags: profileForm.elements.tags.value
      .split(/[,，]/)
      .map((tag) => tag.trim())
      .filter(Boolean),
    wechat: profileForm.elements.wechat.value.trim(),
    wechatQr: allowedImage(profileForm.elements.wechatQr.value.trim()),
    douyin: allowedUrl(profileForm.elements.douyin.value.trim()),
  };
}

function renderPublic(profile, token = "") {
  const displayToken = token || state.me?.necklaceToken || state.token || DEFAULT_TOKEN;
  document.querySelector("#public-handle").textContent = `网站后缀 /tap/${displayToken}`;
  document.querySelector("#public-name").textContent = profile.name || "未命名主页";
  document.querySelector("#public-bio").textContent = profile.bio || "这个主页还在编辑中。";
  document.querySelector("#public-wechat-id").textContent = profile.wechat || "还未填写";
  document.querySelector("#public-token").textContent = displayToken;

  const avatar = document.querySelector("#public-avatar");
  avatar.src = profile.avatar || fallbackAvatar;
  avatar.onerror = () => {
    avatar.src = fallbackAvatar;
  };

  const tagsRoot = document.querySelector("#public-tags");
  tagsRoot.replaceChildren();
  (profile.tags?.length ? profile.tags : ["已绑定"]).forEach((tag) => {
    const chip = document.createElement("span");
    chip.textContent = tag;
    tagsRoot.append(chip);
  });

  const douyin = document.querySelector("#public-douyin");
  douyin.href = profile.douyin || "#";
  douyin.classList.toggle("is-disabled", !profile.douyin);
  douyin.setAttribute("aria-disabled", String(!profile.douyin));
  douyin.tabIndex = profile.douyin ? 0 : -1;
}

function openWechat(profile) {
  if (!profile) return;
  state.publicProfile = profile;
  document.querySelector("#wechat-dialog-title").textContent = `${profile.name || "Ta"} 的微信好友码`;
  document.querySelector("#dialog-copy-wechat").disabled = !profile.wechat;
  document.querySelector("#wechat-dialog-hint").textContent = profile.wechatQr
    ? "长按好友码保存，再去微信扫一扫添加。"
    : "这个主页还没有保存微信好友码图片。";

  const image = document.querySelector("#wechat-qr-image");
  const empty = document.querySelector("#wechat-qr-empty");
  image.hidden = !profile.wechatQr;
  empty.hidden = Boolean(profile.wechatQr);
  image.src = assetUrl(profile.wechatQr);
  wechatDialog.showModal();
}

async function copyWechat(profile) {
  if (!profile?.wechat) return;
  await copyText(profile.wechat, "微信号已复制。");
}

async function copyPublicUrl() {
  const token = state.selectedDevice || state.me?.necklaceToken || state.token;
  if (!token) return;
  await copyText(`${window.location.origin}/tap/${token}`, "公开链接已复制。");
}

function loadQrFile(event) {
  const [file] = event.target.files;
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("#editor-status", "请上传图片格式的微信好友码。");
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    profileForm.elements.wechatQr.value = String(reader.result || "");
    setStatus("#editor-status", "好友码已放进表单，保存后生效。");
  });
  reader.readAsDataURL(file);
}

function loadAvatarFile(event) {
  const [file] = event.target.files;
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("#editor-status", "请上传图片格式的头像。");
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    const value = String(reader.result || "");
    profileForm.dataset.avatar = value;
    updateAvatarPreview(value);
    setStatus("#editor-status", "头像已放进表单，保存后生效。");
  });
  reader.readAsDataURL(file);
}

async function submitRegister(form, token, statusTarget) {
  const data = new FormData(form);
  const result = await api("/api/register", {
    method: "POST",
    body: {
      token,
      name: data.get("name"),
      email: data.get("email"),
      password: data.get("password"),
    },
  });
  if (!result.ok) {
    setStatus(statusTarget, result.error);
  }
  return result;
}

async function submitLogin(form, token, statusTarget) {
  const data = new FormData(form);
  const result = await api("/api/login", {
    method: "POST",
    body: {
      token,
      email: data.get("email"),
      password: data.get("password"),
    },
  });
  if (!result.ok) {
    setStatus(statusTarget, result.error);
  }
  return result;
}

async function logout() {
  await api("/api/logout", { method: "POST", body: {} });
  window.location.href = "/";
}

function updateSessionUi() {
  document.querySelector("#logout-button").hidden = !state.me;
  document.querySelector("#account-link").textContent = state.me ? "我的设备" : "登录 / 管理后台";
}

function tokenFromPath() {
  const match = window.location.pathname.match(/^\/tap\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : "";
}

function deviceTokenFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return params.get("device") || "";
}

function profileSlugFromPath() {
  const match = window.location.pathname.match(/^\/u\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    cache: "no-store",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  return response.ok ? { ok: true, ...data } : { ok: false, error: data.error || "请求失败。" };
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    const target = wechatDialog.open ? "#wechat-dialog-hint" : "#editor-status";
    setStatus(target, message);
  } catch {
    setStatus("#editor-status", "浏览器不允许复制，请手动选择文本。");
  }
}

function allowedUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : "";
  } catch {
    return "";
  }
}

function allowedImage(value) {
  if (value.startsWith("/assets/") || value.startsWith("./assets/")) return value;
  return value.startsWith("data:image/") ? value : allowedUrl(value);
}

function assetUrl(value = "") {
  return value.startsWith("./") ? `/${value.slice(2)}` : value;
}

function updateAvatarPreview(value = "") {
  const preview = document.querySelector("#editor-avatar-preview");
  const source = assetUrl(value) || fallbackAvatar;
  profileForm.dataset.avatar = value || "";
  preview.src = source;
  preview.onerror = () => {
    preview.src = fallbackAvatar;
  };
}

function setStatus(selector, message) {
  const target = document.querySelector(selector);
  if (target) target.textContent = message || "";
}
