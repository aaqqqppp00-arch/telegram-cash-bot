// تهيئة تليجرام ويب آب
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
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

// الشاشات
const screenHome = document.getElementById("screen-home");
const screenWithdraw = document.getElementById("screen-withdraw");
const screenHistory = document.getElementById("screen-history");

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
let rewardAmount = 0.05;
let adsgramBlockId = "";
let adController = null;
let isTapping = false;

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
    alertBox.scrollIntoView({ behavior: "smooth" });
    
    setTimeout(() => {
        alertBox.className = "alert-box hidden";
    }, 4500);
}

// التنقل بين الشاشات
function showScreen(screen) {
    screenHome.classList.add("hidden");
    screenWithdraw.classList.add("hidden");
    screenHistory.classList.add("hidden");
    screen.classList.remove("hidden");
}

btnGoWithdraw.addEventListener("click", () => showScreen(screenWithdraw));
btnGoHistory.addEventListener("click", () => {
    showScreen(screenHistory);
    loadWithdrawalHistory();
});
btnBackFromWithdraw.addEventListener("click", () => showScreen(screenHome));
btnBackFromHistory.addEventListener("click", () => showScreen(screenHome));

// تحديث شريط وبيانات الطاقة
function updateEnergyDisplay() {
    minerEnergyEl.innerText = `${currentEnergy} / ${maxEnergy}`;
    const pct = Math.max(0, Math.min(100, (currentEnergy / maxEnergy) * 100));
    energyProgress.style.width = `${pct}%`;
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
    tapGainLabel.innerText = `+${minerLevel} عملة لكل ضغطة`;
    upgradeBtnText.innerText = `ترقية جهاز التعدين (${minerLevel * 100} عملة)`;
    updateEnergyDisplay();
}

// استرجاع طاقة تدريجي محلياً كل 3 ثواني
setInterval(() => {
    if (currentEnergy < maxEnergy) {
        currentEnergy = Math.min(maxEnergy, currentEnergy + 1);
        updateEnergyDisplay();
    }
}, 3000);

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
            updateUIFromUser(data.user);
            minWithdrawal = data.config.min_withdrawal;
            rewardAmount = data.config.reward_per_ad;
            adsgramBlockId = data.config.adsgram_block_id;

            userGreeting.innerText = `أهلاً بيك يا ${data.user.first_name || "المعدّن"}`;
            minTokensText.innerText = (minWithdrawal * 100).toLocaleString();
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

// الضغط للتعدين (Tap to Mine)
btnMineTap.addEventListener("click", async () => {
    if (currentEnergy <= 0) {
        showAlert("طاقتك خلصت! اشحن الطاقة فوراً بالزرار الأخضر بمشاهدة فيديو أو انتظر شوية.", "info");
        return;
    }

    // تحديث محلي سريع وتفاعلي
    currentEnergy--;
    currentTokens += minerLevel;
    currentBalance = Math.round((currentTokens / 100.0) * 100) / 100;
    
    userTokensEl.innerText = currentTokens.toLocaleString();
    userBalanceEl.innerText = currentBalance.toFixed(2);
    updateEnergyDisplay();

    if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
    }

    // إرسال الضغطة للسيرفر
    if (!isTapping) {
        isTapping = true;
        try {
            const res = await fetch("/api/tap", {
                method: "POST",
                headers: {
                    "X-Telegram-Init-Data": initData
                }
            });
            const data = await res.json();
            if (data.success && data.user) {
                updateUIFromUser(data.user);
            }
        } catch (e) {
            console.error("Tap error:", e);
        } finally {
            isTapping = false;
        }
    }
});

// ترقية جهاز التعدين بالعملات المجمعة
btnUpgradeMiner.addEventListener("click", async () => {
    const cost = minerLevel * 100;
    if (currentTokens < cost) {
        showAlert(`محتاج ${cost} عملة عشان ترقي جهاز التعدين للمستوى التالي. واصل التعدين!`, "info");
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
            showAlert(data.message || "تمت ترقية جهاز التعدين بنجاح!", "success");
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred("success");
            }
        } else {
            showAlert(data.message || "فشلت الترقية", "error");
        }
    } catch (e) {
        showAlert("حصلت مشكلة في الترقية، اتأكد من النت عندك.", "error");
    } finally {
        btnUpgradeMiner.disabled = false;
    }
});

// شحن الطاقة بالكامل بمشاهدة الفيديو (Adsgram Booster)
btnWatchAd.addEventListener("click", async () => {
    btnWatchAd.disabled = true;
    btnWatchAd.querySelector(".btn-text").innerText = "بيجهز الفيديو...";

    // وضع تجريبي إذا لم يتفعل البلوك بعد
    if (!adController || adsgramBlockId === "YOUR_ADSGRAM_BLOCK_ID") {
        const simulate = confirm("تنبيه: هل تود محاكاة مشاهدة الفيديو لشحن الطاقة وإضافة العملات؟");
        if (simulate) {
            await creditRewardAndRefill();
        } else {
            btnWatchAd.disabled = false;
            btnWatchAd.querySelector(".btn-text").innerText = "شحن الطاقة بالكامل فوراً (مشاهدة فيديو)";
        }
        return;
    }

    // تشغيل الفيديو عبر Adsgram
    adController.show().then(async (result) => {
        showAlert("عاش! شوفت الفيديو كامل، بنشحنلك الطاقة والعملات...", "info");
        await creditRewardAndRefill();
    }).catch((result) => {
        let msg = "مشوفتش الفيديو للآخر، فالطاقة متجددتش.";
        if (result && result.description) {
            if (result.description.includes("no ads") || result.description.includes("empty")) {
                msg = "مفيش فيديوهات متاحة حالياً، جرب تاني بعد دقيقة.";
            }
        }
        showAlert(msg, "error");
        btnWatchAd.disabled = false;
        btnWatchAd.querySelector(".btn-text").innerText = "شحن الطاقة بالكامل فوراً (مشاهدة فيديو)";
    });
});

// تأكيد مكافأة الإعلان وشحن الطاقة
async function creditRewardAndRefill() {
    try {
        const res = await fetch("/api/claim-ad", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();
        
        if (data.success && data.user) {
            updateUIFromUser(data.user);
            showAlert("مبروك! تم شحن الطاقة بالكامل ونزلت مكافأة الفيديو في رصيدك.", "success");
            
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred("success");
            }
        } else {
            showAlert(data.message || "حصلت مشكلة في الشحن", "error");
        }
    } catch (err) {
        console.error("Reward error:", err);
        showAlert("فشل الشحن، اتأكد من النت عندك.", "error");
    } finally {
        btnWatchAd.disabled = false;
        btnWatchAd.querySelector(".btn-text").innerText = "شحن الطاقة بالكامل فوراً (مشاهدة فيديو)";
    }
}

// نموذج السحب واستبدال العملات
withdrawForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const selectedProvider = document.querySelector('input[name="provider"]:checked').value;
    const phone = withdrawPhone.value.trim();
    const amount = parseFloat(withdrawAmount.value);

    if (!phone || phone.length !== 11) {
        showAlert("لازم تكتب رقم موبايل صح مكون من 11 رقم", "error");
        return;
    }

    if (isNaN(amount) || amount < minWithdrawal) {
        showAlert(`أقل حد للسحب هو ${minWithdrawal} جنيه (${minWithdrawal * 100} عملة)`, "error");
        return;
    }

    if (amount > currentBalance) {
        showAlert(`رصيدك الحالي (${currentTokens} عملة = ${currentBalance.toFixed(2)} ج) ميكفيش تسحب المبلغ ده!`, "error");
        return;
    }

    const confirmWithdraw = confirm(`تأكيد استبدال العملات:\n\nالمحفظة: ${selectedProvider}\nالرقم: ${phone}\nالمبلغ المطلوب: ${amount} جنيه (${amount * 100} عملة)\n\nالبيانات كده صح؟`);
    if (!confirmWithdraw) return;

    const btnSubmit = document.getElementById("btn-submit-withdraw");
    btnSubmit.disabled = true;
    btnSubmit.innerText = "بيبعت الطلب...";

    try {
        const res = await fetch("/api/withdraw", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Telegram-Init-Data": initData
            },
            body: JSON.stringify({
                provider: selectedProvider,
                phone_number: phone,
                amount: amount
            })
        });

        const data = await res.json();
        if (data.success) {
            showAlert("تم إرسال طلب استبدال العملات بنجاح، هيتم تحويل الكاش لمحفظتك قريباً.", "success");
            currentBalance -= amount;
            currentTokens = Math.round(currentBalance * 100);
            userBalanceEl.innerText = currentBalance.toFixed(2);
            userTokensEl.innerText = currentTokens.toLocaleString();
            withdrawPhone.value = "";
            withdrawAmount.value = "";
            setTimeout(() => {
                showScreen(screenHome);
            }, 1800);
        } else {
            showAlert(data.message || "فشل إرسال الطلب", "error");
        }
    } catch (err) {
        console.error("Withdraw error:", err);
        showAlert("حصلت مشكلة في الاتصال بالسيرفر.", "error");
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerText = "تأكيد طلب السحب";
    }
});

// تحميل سجل العمليات
async function loadWithdrawalHistory() {
    historyList.innerHTML = '<p class="empty-msg">بيحمل السجل...</p>';
    try {
        const res = await fetch("/api/withdrawals", {
            headers: {
                "X-Telegram-Init-Data": initData
            }
        });
        const data = await res.json();

        if (data.success && data.withdrawals && data.withdrawals.length > 0) {
            historyList.innerHTML = data.withdrawals.map(w => {
                let badgeClass = "badge-pending";
                let statusText = "قيد المراجعة";
                if (w.status === "approved") {
                    badgeClass = "badge-approved";
                    statusText = "تم التحويل بنجاح";
                } else if (w.status === "rejected") {
                    badgeClass = "badge-rejected";
                    statusText = "مرفوض والعملات رجعت لرصيدك";
                }

                let provName = "فودافون كاش";
                if (w.provider === "orange_cash") provName = "أورنج كاش";
                if (w.provider === "etisalat_cash") provName = "اتصالات كاش";
                if (w.provider === "we_cash") provName = "وي كاش";

                const dateStr = new Date(w.created_at * 1000).toLocaleDateString('ar-EG');

                return `
                    <div class="history-item">
                        <div class="history-header">
                            <span>${w.amount.toFixed(2)} جنيه (${provName})</span>
                            <span class="badge ${badgeClass}">${statusText}</span>
                        </div>
                        <div class="history-details">
                            <div>الرقم: <b>${w.phone_number}</b></div>
                            <div>التاريخ: ${dateStr}</div>
                        </div>
                    </div>
                `;
            }).join("");
        } else {
            historyList.innerHTML = '<p class="empty-msg">مفيش أي عمليات سابقة لحد دلوقتي.</p>';
        }
    } catch (err) {
        historyList.innerHTML = '<p class="empty-msg">فشل تحميل السجل.</p>';
    }
}

// بدء التحميل
loadUserData();
