// 全局GET请求
async function httpGet(url) {
    let token = localStorage.getItem("token");
    let headers = {};
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }

    let res = await fetch(url, {
        headers: headers
    });
    let json = await res.json();
    if (json.code !== 200) {
        console.log("HTTP Error:", url, json);
    }
    return json;
}

// 全局POST请求
async function httpPost(url, data = {}) {
    let token = localStorage.getItem("token");
    let headers = {
        "Content-Type": "application/json"
    };
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }

    let res = await fetch(url, {
        method: "POST",
        headers: headers,
        body: JSON.stringify(data)
    });
    return await res.json();
}

// 全局DELETE请求
async function httpDelete(url) {
    let token = localStorage.getItem("token");
    let headers = {};
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }

    let res = await fetch(url, {
        method: "DELETE",
        headers: headers
    });
    return await res.json();
}

// 全局PUT请求
async function httpPut(url, data = {}) {
    let token = localStorage.getItem("token");
    let headers = {
        "Content-Type": "application/json"
    };
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }

    let res = await fetch(url, {
        method: "PUT",
        headers: headers,
        body: JSON.stringify(data)
    });
    return await res.json();
}

function logout() {
    localStorage.removeItem("token");
    showAlert("已退出登录", "success");
    setTimeout(() => {
        location.href = "/api/auth/login/page";
    }, 1000);
}

function toggleUserMenu() {
    const menu = document.getElementById("userMenu");
    if (menu) {
        menu.style.display = menu.style.display === "none" ? "block" : "none";
    }
}

document.addEventListener("click", function(e) {
    const menu = document.getElementById("userMenu");
    if (menu && !e.target.closest('[onclick*="toggleUserMenu"]')) {
        menu.style.display = "none";
    }
});

function checkLogin() {
    const token = localStorage.getItem("token")
    const isLoginPage = location.pathname.includes("/login/page");
    if (!token && !isLoginPage) {
        window.location.href = "/api/auth/login/page";
    }
}

document.addEventListener('DOMContentLoaded', function () {
    checkLogin();
});

function showAlert(msg, type = "info") {
    // 先删掉旧的提示框
    let old = document.querySelector(".toast-container");
    if (old) old.remove();

    // 创建容器
    let toast = document.createElement("div");
    toast.className = "toast-container";

    // 样式
    toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 6px;
        color: #fff;
        font-size: 14px;
        z-index: 9999;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        animation: slideIn 0.3s ease;
    `;

    // 颜色
    if (type === "success") {
        toast.style.background = "#28a745";
    } else if (type === "error") {
        toast.style.background = "#dc3545";
    } else if (type === "warning") {
        toast.style.background = "#ffc107";
        toast.style.color = "#333";
    } else {
        toast.style.background = "#17a2b8";
    }

    // 内容
    toast.innerText = msg;
    document.body.appendChild(toast);

    // 3秒自动消失
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// 动画
let style = document.createElement("style");
style.innerHTML = `
@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
`;
document.head.appendChild(style);


// ============================
// 全局角色渲染 & 菜单权限控制
// 所有页面自动生效
// ============================
document.addEventListener('DOMContentLoaded', function () {
    const role = localStorage.getItem('role');

    // 1. 显示角色文字
    const roleTextEl = document.getElementById('roleText');
    if (roleTextEl) {
        const username = localStorage.getItem('username') || '';
        const roleText = role === 'admin' ? '管理员' : '普通用户';
        roleTextEl.innerText = username ? `${username}（${roleText}）` : '';
    }

    // 2. 权限控制：管理员菜单
    const userManageMenu = document.getElementById('userManageMenu');
    if (userManageMenu) {
        if (role === 'admin') {
            userManageMenu.style.display = 'block';
        } else {
            userManageMenu.style.display = 'none';
        }
    }

    // 3. 操作日志菜单（仅管理员可见）
    const operationLogMenu = document.getElementById('operationLogMenu');
    if (operationLogMenu) {
        if (role === 'admin') {
            operationLogMenu.style.display = 'block';
        } else {
            operationLogMenu.style.display = 'none';
        }
    }

    const reportMenu = document.getElementById('reportMenu');
    if (reportMenu) {
        if (role === 'admin') {
            reportMenu.style.display = 'block';
        } else {
            reportMenu.style.display = 'none';
        }
    }
});
