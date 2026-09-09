// تهيئة تليجرام ويب آب ومنع السكرول والاهتزاز الرأسي
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.disableVerticalSwipes) {
        tg.disableVerticalSwipes();
    }
}

// عناصر واجهة اللعبة
const userGreeting = document.getElementById("user-greeting");
const userTokensEl = document.getElementById("user-tokens");
const userBalanceEl = document.getElementById("user-balance");
const minerLevelEl = document.getElementById("miner-level");
const minerEnergyEl = document.getElementById("miner-energy");
const energyProgress = document.getElementById("energy-progress");
const tapGainLabel = document.getElementById("tap-gain-label");
const upgradeBtnText = document.getElementById("upgrade-btn-text");
const minTokensText = document.getElementById("min-tokens-text");
const minWithdrawText = document.getElementById("min-withdraw-text");
const alertBox = document.getElementById("alert-box");
const tapParticles = document.getElementById("tap-particles");

// الشاشات
const screenHome = document.getElementById("screen-home");
const screenWithdraw = document.getElementById("screen-withdraw");
const screenHistory = document.getElementById("screen-history");
const screenProofs = document.getElementById("screen-proofs");
const screenLeaderboard = document.getElementById("screen-leaderboard");
const btnGoProofs = document.getElementById("btn-go-proofs");
const btnGoLeaderboard = document.getElementById("btn-go-leaderboard");
const btnBackFromProofs = document.getElementById("btn-back-from-proofs");
const btnBackFromLeaderboard = document.getElementById("btn-back-from-leaderboard");
const proofsList = document.getElementById("proofs-list");
const leaderboardList = document.getElementById("leaderboard-list");


// الأزرار
const btnMineTap = document.getElementById("btn-mine-tap");
const btnWatchAd = document.getElementById("btn-watch-ad");
const btnUpgradeMiner = document.getElementById("btn-upgrade-miner");
const btnGoWithdraw = document.getElementById("btn-go-withdraw");
const btnGoHistory = document.getElementById("btn-go-history");
const btnBackFromWithdraw = document.getElementById("btn-back-from-withdraw");
const btnBackFromHistory = document.getElementById("btn-back-from-history");

// نموذج السحب
const withdrawForm = document.getElementById("withdraw-form");
const withdrawPhone = document.getElementById("withdraw-phone");
const withdrawAmount = document.getElementById("withdraw-amount");
const historyList = document.getElementById("history-list");

// متغيرات الحالة واللعبة
let currentBalance = 0.0;
let currentTokens = 0;
let currentEnergy = 100;
let maxEnergy = 100;
let minerLevel = 1;
let minWithdrawal = 20.0;
let tokensPerEgp = 5000;
let rewardAmount = 0.05;
let adsgramBlockId = "";
let adController = null;

// نظام تجميع الضغطات لمنع أي فقدان أو قفزات في العداد
let pendingTaps = 0;
let syncTimer = null;
let isSyncing = false;

// التحقق من هوية تليجرام
const initData = tg?.initData || "user=" + encodeURIComponent(JSON.stringify({
    id: 999999999,
    first_name: "مستخدم تجريبي",
    username: "test_user"
})) + "&hash=mock";

// إظهار التنبيهات بدون إيموجي
function showAlert(message, type = "info") {
    alertBox.className = `alert-box ${type}`;
    alertBox.innerText = message;
    
    setTimeout(() => {
        alertBox.className = "alert-box hidden";
    }, 4000);
}

// التنقل بين الشاشات

// دوال التنقل العامة المتاحة للأزرار المباشرة
window.openProofsScreen = function() {
    showScreen(document.getElementById("screen-proofs") || screenProofs);
    loadPublicProofs();
};

window.openLeaderboardScreen = function() {
    showScreen(document.getElementById("screen-leaderboard") || screenLeaderboard);
    loadLeaderboard();
};

window.openHomeScreen = function() {
    showScreen(document.getElementById("screen-home") || screenHome);
};

window.openWithdrawScreen = function() {
    showScreen(document.getElementById("screen-withdraw") || screenWithdraw);
};

window.openHistoryScreen = function() {
    showScreen(document.getElementById("screen-history") || screenHistory);
    loadWithdrawalHistory();
};

function showScreen(screen) {
    screenHome.classList.add("hidden");
    screenWithdraw.classList.add("hidden");
    screenHistory.classList.add("hidden");
    if (screenProofs) screenProofs.classList.add("hidden");
    if (screenLeaderboard) screenLeaderboard.classList.add("hidden");
    screen.classList.remove("hidden");
}

btnGoWithdraw.addEventListener("click", () => showScreen(screenWithdraw));
btnGoHistory.addEventListener("click", () => {
    showScreen(screenHistory);
    loadWithdrawalHistory();
});
btnBackFromWithdraw.addEventListener("click", () => showScreen(screenHome));
btnBackFromHistory.addEventListener("click", () => showScreen(screenHome));

if (btnGoProofs) btnGoProofs.addEventListener("click", () => {
    showScreen(screenProofs);
    loadPublicProofs();
});
if (btnGoLeaderboard) btnGoLeaderboard.addEventListener("click", () => {
    showScreen(screenLeaderboard);
    loadLeaderboard();
});
if (btnBackFromProofs) btnBackFromProofs.addEventListener("click", () => showScreen(screenHome));
if (btnBackFromLeaderboard) btnBackFromLeaderboard.addEventListener("click", () => showScreen(screenHome));


// تحديث شريط وبيانات الطاقة
function updateEnergyDisplay() {
    minerEnergyEl.innerText = `${currentEnergy} / ${maxEnergy}`;
    const pct = Math.max(0, Math.min(100, (currentEnergy / maxEnergy) * 100));
    energyProgress.style.width = `${pct}%`;

    const countdownEl = document.getElementById("energy-countdown");
    if (countdownEl) {
        if (currentEnergy >= maxEnergy) {
            countdownEl.innerText = "الطاقة ممتلئة بالكامل";
        } else {
            const needed = maxEnergy - currentEnergy;
            const hrs = Math.floor(needed / 60);
            const mins = needed % 60;
            if (hrs > 0) {
                countdownEl.innerText = `لاكتمال الطاقة: متبقي ${hrs} س و ${mins} د`;
            } else {
                countdownEl.innerText = `لاكتمال الطاقة: متبقي ${mins} دقيقة`;
            }
        }
    }
}

// تحديث عرض البيانات على الشاشة
function updateUIFromUser(user) {
    currentTokens = user.tokens || 0;
    currentBalance = user.balance || 0.0;
    currentEnergy = user.energy || 0;
    maxEnergy = user.max_energy || 100;
    minerLevel = user.miner_level || 1;

    userTokensEl.innerText = currentTokens.toLocaleString();
    userBalanceEl.innerText = currentBalance.toFixed(2);
    minerLevelEl.innerText = `مستوى ${minerLevel} (+${minerLevel})`;
    tapGainLabel.innerText = `+${minerLevel} عملة لكل نقرة`;
    upgradeBtnText.innerText = `ترقية جهاز التعدين (${minerLevel * 500} عملة)`;
    updateEnergyDisplay();
}

// استرجاع طاقة بطيء جداً محلياً (نقطة واحدة كل دقيقة = 60 ثانية)
setInterval(() => {
    if (currentEnergy < maxEnergy) {
        currentEnergy = Math.min(maxEnergy, currentEnergy + 1);
        updateEnergyDisplay();
    }
}, 60000);

// جلب بيانات المستخدم من السيرفر
async function loadUserData() {
    try {
        const res = await fetch("/api/user-info", {
            headers: {
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();
        
        if (data.success) {
            tokensPerEgp = data.config.tokens_per_egp || 5000;
            minWithdrawal = data.config.min_withdrawal || 20.0;
            rewardAmount = data.config.reward_per_ad || 0.05;
            adsgramBlockId = data.config.adsgram_block_id;

            updateUIFromUser(data.user);

            userGreeting.innerText = `أهلاً بيك يا ${data.user.first_name || "المعدّن"}`;
            minTokensText.innerText = (minWithdrawal * tokensPerEgp).toLocaleString();
            minWithdrawText.innerText = minWithdrawal.toFixed(0);

            initAdsgram();
        } else {
            showAlert("حصلت مشكلة في تحميل بيانات التعدين: " + (data.error || ""), "error");
        }
    } catch (err) {
        console.error("Error loading user data:", err);
        showAlert("مش عارفين نوصل للسيرفر، اتأكد من النت عندك.", "error");
    }
}

// تهيئة Adsgram SDK
function initAdsgram() {
    if (window.Adsgram && adsgramBlockId && adsgramBlockId !== "YOUR_ADSGRAM_BLOCK_ID") {
        try {
            adController = window.Adsgram.init({ blockId: adsgramBlockId });
        } catch (e) {
            console.error("Failed to init Adsgram:", e);
        }
    }
}

// إظهار رقم عائم مكان النقرة (+1)
function spawnTapPop(clientX, clientY, amount) {
    try {
        if (!tapParticles) return;
        const stageRect = tapParticles.getBoundingClientRect();
        let x = stageRect.width / 2;
        let y = stageRect.height / 2;

        if (clientX && clientX > 0 && stageRect.left !== undefined) {
            x = Math.max(20, Math.min(stageRect.width - 20, clientX - stageRect.left));
        }
        if (clientY && clientY > 0 && stageRect.top !== undefined) {
            y = Math.max(20, Math.min(stageRect.height - 20, clientY - stageRect.top));
        }

        const pop = document.createElement("span");
        pop.className = "tap-pop";
        pop.innerText = `+${amount}`;
        pop.style.left = `${x}px`;
        pop.style.top = `${y}px`;

        tapParticles.appendChild(pop);

        setTimeout(() => {
            pop.remove();
        }, 450);
    } catch (err) {
        console.warn("spawnTapPop error:", err);
    }
}

// معالجة النقر محلياً وفورياً
function handleTap(clientX, clientY) {
    if (currentEnergy <= 0) {
        showAlert("طاقتك خلصت! اضغط على الزرار الأخضر واتفرج على فيديو لشحن الطاقة وكمل تعدين.", "info");
        return;
    }

    // استهلاك نقطة طاقة وإضافة عملات محلياً في التو واللحظة
    currentEnergy--;
    currentTokens += minerLevel;
    currentBalance = Math.round((currentTokens / tokensPerEgp) * 100) / 100;
    pendingTaps++;

    userTokensEl.innerText = currentTokens.toLocaleString();
    userBalanceEl.innerText = currentBalance.toFixed(2);
    updateEnergyDisplay();

    // اهتزاز تليجرام الخفيف
    if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
    }

    // إظهار الرقم العائم
    spawnTapPop(clientX, clientY, minerLevel);

    // جدولة إرسال الضغطات المجمعة للسيرفر
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(syncTapsWithServer, 400);
}

// مزامنة حزمة الضغطات مع السيرفر بدقة تامة
async function syncTapsWithServer() {
    if (pendingTaps <= 0 || isSyncing) return;

    const countToSend = pendingTaps;
    isSyncing = true;

    try {
        const res = await fetch("/api/tap", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Telegram-Init-Data": initData
            },
            body: JSON.stringify({ count: countToSend })
        });
        const data = await res.json();

        if (data.success && data.user) {
            // خصم ما تم تأكيده من طابور الانتظار
            pendingTaps = Math.max(0, pendingTaps - countToSend);

            // دمج حالة السيرفر مع أي ضغطات حصلت أثناء وقت استجابة الشبكة
            currentTokens = data.user.tokens + (pendingTaps * minerLevel);
            currentBalance = Math.round((currentTokens / tokensPerEgp) * 100) / 100;
            currentEnergy = Math.max(0, data.user.energy - pendingTaps);

            userTokensEl.innerText = currentTokens.toLocaleString();
            userBalanceEl.innerText = currentBalance.toFixed(2);
            updateEnergyDisplay();
        }
    } catch (err) {
        console.error("Tap sync error:", err);
    } finally {
        isSyncing = false;
        if (pendingTaps > 0) {
            if (syncTimer) clearTimeout(syncTimer);
            syncTimer = setTimeout(syncTapsWithServer, 400);
        }
    }
}

// نظام التقاط النقرات الفوري الشامل لكل أنواع الأجهزة (لمس، ماوس، كمبيوتر، موبايل)
let lastTapTimestamp = 0;

function onUserTap(e) {
    if (e) {
        if (e.stopPropagation) e.stopPropagation();
        if (e.cancelable && e.type !== "click") {
            e.preventDefault();
        }
    }

    const now = Date.now();
    if (now - lastTapTimestamp < 80) {
        return; // منع الضغط المزدوج المكرر من نفس الحدث
    }
    lastTapTimestamp = now;

    let clientX = 0;
    let clientY = 0;
    if (e) {
        if (e.touches && e.touches.length > 0) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else if (e.clientX !== undefined) {
            clientX = e.clientX;
            clientY = e.clientY;
        }
    }

    handleTap(clientX, clientY);
}

// جعلها عامة للوصول إليها
window.onUserTap = onUserTap;

if (btnMineTap) {
    // 1. استجابة 0ms بـ pointerdown لجميع الشاشات
    btnMineTap.addEventListener("pointerdown", onUserTap, { passive: false });
    // 2. كليك أساسي لمتصفحات تليجرام المختلفة
    btnMineTap.addEventListener("click", onUserTap);
    // 3. لمس مباشر للموبايل القديم
    btnMineTap.addEventListener("touchstart", onUserTap, { passive: false });
}

// إتاحة النقر في كامل مساحة التعدين لسهولة اللعب
const miningStage = document.querySelector(".mining-stage");
if (miningStage) {
    miningStage.addEventListener("pointerdown", (e) => {
        if (e.target === miningStage || (e.target && e.target.id === "tap-particles")) {
            onUserTap(e);
        }
    }, { passive: false });
}

// مزامنة فورية عند مغادرة الصفحة أو قفل التطبيق
window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && pendingTaps > 0) {
        syncTapsWithServer();
    }
});

// ترقية مستوى التعدين
btnUpgradeMiner.addEventListener("click", async () => {
    const upgradeCost = minerLevel * 500;
    if (currentTokens < upgradeCost) {
        showAlert(`محتاج ${upgradeCost.toLocaleString()} عملة للترقية، رصيدك الحالي مش كفاية.`, "error");
        return;
    }

    btnUpgradeMiner.disabled = true;
    try {
        const res = await fetch("/api/upgrade", {
            method: "POST",
            headers: {
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();
        if (data.success && data.user) {
            updateUIFromUser(data.user);
            showAlert(`مبروك! تمت الترقية للمستوى ${data.user.miner_level} وضاعفت أرباحك!`, "success");
        } else {
            showAlert(data.message || "فشلت الترقية", "error");
        }
    } catch (e) {
        showAlert("حصل خطأ أثناء الترقية، جرب تاني.", "error");
    } finally {
        btnUpgradeMiner.disabled = false;
    }
});

// شحن الطاقة بمشاهدة الفيديو (Adsgram Booster)
btnWatchAd.addEventListener("click", async () => {
    btnWatchAd.disabled = true;
    const originalText = btnWatchAd.innerHTML;
    btnWatchAd.innerHTML = "<span class=\"btn-text\">جاري تشغيل الفيديو...</span>";

    if (adController) {
        adController.show().then(() => {
            claimReward(originalText);
        }).catch((result) => {
            console.warn("Ad skipped or failed:", result);
            btnWatchAd.disabled = false;
            btnWatchAd.innerHTML = originalText;
            showAlert("تم إلغاء الفيديو أو لم يكتمل، اتفرج للآخر لشحن الطاقة.", "error");
        });
    } else {
        // محاكاة وضع التطوير المحلي
        setTimeout(() => {
            claimReward(originalText);
        }, 1200);
    }
});

// تأكيد مكافأة الإعلان وشحن الطاقة
async function claimReward(originalBtnText) {
    try {
        const res = await fetch("/api/claim-ad", {
            method: "POST",
            headers: {
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();

        if (data.success) {
            showAlert("تم شحن طاقة البطارية بالكامل وإضافة عملات بونص بنجاح!", "success");
            if (data.user) {
                updateUIFromUser(data.user);
            } else {
                currentEnergy = maxEnergy;
                updateEnergyDisplay();
            }
        } else {
            showAlert(data.message || "حصلت مشكلة في إضافة المكافأة", "error");
        }
    } catch (err) {
        console.error("Error claiming reward:", err);
        showAlert("مش عارفين نسجل المكافأة، اتأكد من اتصال النت.", "error");
    } finally {
        btnWatchAd.disabled = false;
        btnWatchAd.innerHTML = originalBtnText;
    }
}

// تقديم طلب سحب
withdrawForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const providerEl = document.querySelector('input[name="provider"]:checked');
    const provider = providerEl ? providerEl.value : "vodafone_cash";
    const phone = withdrawPhone.value.trim();
    const amount = parseFloat(withdrawAmount.value);

    if (amount < minWithdrawal) {
        showAlert(`أقل حد للسحب هو ${minWithdrawal} جنيه.`, "error");
        return;
    }

    if (amount > currentBalance) {
        showAlert(`رصيدك الحالي (${currentBalance.toFixed(2)} ج) ميكفيش للمبلغ المطلوب.`, "error");
        return;
    }

    const submitBtn = document.getElementById("btn-submit-withdraw");
    submitBtn.disabled = true;
    submitBtn.innerText = "جاري إرسال الطلب...";

    try {
        const res = await fetch("/api/withdraw", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Telegram-Init-Data": initData
            },
            body: JSON.stringify({
                provider: provider,
                phone_number: phone,
                amount: amount
            })
        });
        const data = await res.json();

        if (data.success) {
            showAlert("تم إرسال طلب السحب بنجاح وهيتم التحويل لمحفظتك قريباً.", "success");
            withdrawAmount.value = "";
            showScreen(screenHome);
            loadUserData();
        } else {
            showAlert(data.message || "فشل إرسال طلب السحب.", "error");
        }
    } catch (err) {
        console.error("Withdraw error:", err);
        showAlert("حصلت مشكلة أثناء الاتصال بالسيرفر، جرب تاني.", "error");
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = "تأكيد طلب السحب";
    }
});

// تحميل سجل السحوبات
async function loadWithdrawalHistory() {
    historyList.innerHTML = "<p class='empty-msg'>بيحمل السجل...</p>";

    try {
        const res = await fetch("/api/withdrawals", {
            headers: {
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();

        if (data.success && data.withdrawals && data.withdrawals.length > 0) {
            historyList.innerHTML = "";
            data.withdrawals.forEach(item => {
                const dateStr = new Date(item.created_at * 1000).toLocaleDateString("ar-EG", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit"
                });

                let statusBadge = "";
                if (item.status === "pending") {
                    statusBadge = "<span class='history-status status-pending'>مستني الموافقة</span>";
                } else if (item.status === "approved") {
                    statusBadge = "<span class='history-status status-approved'>تم التحويل</span>";
                } else {
                    statusBadge = "<span class='history-status status-rejected'>مرفوض ومسترد</span>";
                }

                const providerName = {
                    "vodafone_cash": "فودافون كاش",
                    "orange_cash": "أورنج كاش",
                    "etisalat_cash": "اتصالات كاش",
                    "we_cash": "وي كاش"
                }[item.provider] || item.provider;

                const div = document.createElement("div");
                div.className = "history-item";
                div.innerHTML = `
                    <div class="history-top">
                        <span class="history-amount">${item.amount.toFixed(2)} جنيه</span>
                        ${statusBadge}
                    </div>
                    <div class="history-bottom">
                        <span>${providerName} (${item.phone_number})</span>
                        <span>${dateStr}</span>
                    </div>
                `;
                historyList.appendChild(div);
            });
        } else {
            historyList.innerHTML = "<p class='empty-msg'>لسه مفيش أي طلبات سحب سابقة.</p>";
        }
    } catch (err) {
        console.error("Error loading history:", err);
        historyList.innerHTML = "<p class='empty-msg'>حصلت مشكلة في تحميل السجل.</p>";
    }
}


// تحميل إثباتات وتأكيدات الدفع الحية (متوافق مع البند 8)
async function loadPublicProofs() {
    if (!proofsList) return;
    proofsList.innerHTML = "<p class='empty-msg'>بيحمل إثباتات الدفع...</p>";

    try {
        const res = await fetch("/api/proofs");
        const data = await res.json();

        if (data.success && data.proofs && data.proofs.length > 0) {
            proofsList.innerHTML = "";
            data.proofs.forEach(item => {
                const providerName = {
                    "vodafone_cash": "فودافون كاش",
                    "orange_cash": "أورنج كاش",
                    "etisalat_cash": "اتصالات كاش",
                    "we_cash": "وي كاش"
                }[item.provider] || item.provider;

                const div = document.createElement("div");
                div.className = "proof-item";
                div.innerHTML = `
                    <div class="proof-top">
                        <span class="proof-amount">${item.amount.toFixed(2)} جنيه</span>
                        <span class="proof-badge">تحويل ناجح ومؤكد</span>
                    </div>
                    <div class="proof-middle">
                        <span>${item.user_name} (${item.phone_masked})</span>
                        <span>${providerName}</span>
                    </div>
                    <div class="proof-bottom">
                        <span>كود العملية: ${item.id}</span>
                        <span>${item.time_ago}</span>
                    </div>
                `;
                proofsList.appendChild(div);
            });
        } else {
            proofsList.innerHTML = "<p class='empty-msg'>لا توجد إثباتات بعد.</p>";
        }
    } catch (err) {
        console.error("Proofs error:", err);
        proofsList.innerHTML = "<p class='empty-msg'>حصلت مشكلة في تحميل الإثباتات.</p>";
    }
}

// تحميل لوحة المتصدرين وقائمة الشرف (متوافق مع البند 8)
async function loadLeaderboard() {
    if (!leaderboardList) return;
    leaderboardList.innerHTML = "<p class='empty-msg'>بيحمل لوحة المتصدرين...</p>";

    try {
        const res = await fetch("/api/leaderboard");
        const data = await res.json();

        if (data.success && data.leaderboard && data.leaderboard.length > 0) {
            leaderboardList.innerHTML = "";
            data.leaderboard.forEach(item => {
                const rankClass = item.rank <= 3 ? `top-${item.rank}` : "";
                const div = document.createElement("div");
                div.className = "leader-item";
                div.innerHTML = `
                    <div class="leader-rank ${rankClass}">#${item.rank}</div>
                    <div class="leader-info">
                        <div class="leader-name">${item.name}</div>
                        <div class="leader-sub">مستوى التعدين: ${item.level}</div>
                    </div>
                    <div class="leader-stats">
                        <div class="leader-tokens">${item.tokens.toLocaleString()} $WEKI</div>
                        <div class="leader-paid">سحب: ${item.paid_out.toFixed(2)} ج</div>
                    </div>
                `;
                leaderboardList.appendChild(div);
            });
        } else {
            leaderboardList.innerHTML = "<p class='empty-msg'>لا توجد بيانات متصدرين حالياً.</p>";
        }
    } catch (err) {
        console.error("Leaderboard error:", err);
        leaderboardList.innerHTML = "<p class='empty-msg'>حصلت مشكلة في تحميل المتصدرين.</p>";
    }
}

// بدء التشغيل
loadUserData();
