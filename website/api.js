// Shared helpers for talking to the Sentinel backend.
//
// Open the site from the backend (http://localhost:3000/) and API calls go
// to the same origin, so the login cookie is sent automatically. From any
// other origin (e.g. Live Server on :5500) calls go to localhost:3000 with
// credentials included; that origin must be in the backend's CORS_ORIGINS.

const API_BASE =
	window.SENTINEL_API_BASE ?? (location.port === "3000" ? "" : "http://localhost:3000");

// fetch() wrapper: sends JSON, always includes the session cookie, and
// returns { ok, status, data } instead of throwing on HTTP errors.
async function api(path, { method = "GET", body } = {}) {
	const options = { method, credentials: "include", headers: {} };
	if (body !== undefined) {
		options.headers["Content-Type"] = "application/json";
		options.body = JSON.stringify(body);
	}
	try {
		const res = await fetch(API_BASE + "/api" + path, options);
		const text = await res.text();
		let data = null;
		try { data = text ? JSON.parse(text) : null; } catch (_) { data = null; }
		return { ok: res.ok, status: res.status, data };
	} catch (_) {
		return { ok: false, status: 0, data: { error: "network", message: "Can't reach the server. Is the backend running?" } };
	}
}

const auth = {
	login: (username, password) => api("/auth/login", { method: "POST", body: { username, password } }),
	register: (username, password) => api("/auth/register", { method: "POST", body: { username, password } }),
	logout: () => api("/auth/logout", { method: "POST" }),
	// The signed-in user, or null for a guest (or if the server is down).
	async currentUser() {
		const res = await api("/auth/me");
		return res.ok && res.data ? res.data.user : null;
	},
};

function errorMessage(res, fallback) {
	return (res.data && res.data.message) || fallback;
}

// Fills an element (the sidebar's #account box) with who is signed in and a
// log out / log in link. `loginPage` is the path to index.html from the page.
async function renderAccount(elementId, loginPage) {
	const box = document.getElementById(elementId);
	if (!box) return;
	const user = await auth.currentUser();
	box.textContent = "";

	const who = document.createElement("div");
	who.className = "account-name";
	const link = document.createElement("a");
	link.href = loginPage;

	if (user) {
		who.textContent = "Signed in as " + user.username;
		link.textContent = "Log out";
		link.addEventListener("click", async (e) => {
			e.preventDefault();
			await auth.logout();
			window.location.href = loginPage;
		});
	} else {
		who.textContent = "Guest";
		link.textContent = "Log in";
	}
	box.append(who, link);
}
