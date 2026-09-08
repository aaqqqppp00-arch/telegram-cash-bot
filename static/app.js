// تهيئة تليجرام ويب آب
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// عناصر واجهة اللعبة
const userGreeting = document.getElementById("user-greeting");
const userPoints = document.getElementById("user-points");
const userBalance = document.getElementById("user-balance");
const gameAttemptsEl = document.getElementById("game-attempts");
const userAds = document.getElementById("user-ads");
const minPointsText = document.getElementById("min-points-text");
const minWithdrawText = document.getElementById("min-withdraw-text");
const alertBox = document.getElementById("alert-box");

// الشاشات
const screenHome = document.getElementById("screen-home");
const screenWithdraw = document.getElementById("screen-withdraw");
const screenHistory = document.getElementById("screen-history");

// كروت اللعبة
const gameCards = document.querySelectorAll(".game-card");

// الأزرار
const btnWatchAd = document.getElementById("btn-watch-ad");
const btnGoWithdraw = document.getElementById("btn-go-withdraw");
const btnGoHistory = document.getElementById("btn-go-history");
const btnBackFromWithdraw = document.getElementById("btn-back-from-withdraw");
const btnBackFromHistory = document.getElementById("btn-back-from-history");

// نموذج السحب
const withdrawForm = document.getElementById("withdraw-form");
const withdrawPhone = document.getElementById("withdraw-phone");
const withdrawAmount = document.getElementById("withdraw-amount");
const historyList = document.getElementById("history-list");

// متغيرات اللعبة والحالة
let currentBalance = 0; // بالكاش
let currentPoints = 0;  // بالنقاط (1 جنيه = 100 نقطة)
let minWithdrawal = 20;
let rewardAmount = 0.05;
let adsgramBlockId = "";
let adController = null;

// محاولات اللعب (يتم حفظها محلياً لكل جلسة)
let gameAttempts = parseInt(localStorage.getItem("weki_attempts") || "3");

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

// تحديث عرض المحاولات على الشاشة
function updateAttemptsDisplay() {
    gameAttemptsEl.innerText = gameAttempts;
    localStorage.setItem("weki_attempts", gameAttempts.toString());
    
    if (gameAttempts <= 0) {
        btnWatchAd.querySelector(".btn-text").innerText = "شحن 3 محاولات مجاناً (مشاهدة فيديو)";
    }
}

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
            currentBalance = data.user.balance;
            currentPoints = Math.round(currentBalance * 100);
            minWithdrawal = data.config.min_withdrawal;
            rewardAmount = data.config.reward_per_ad;
            adsgramBlockId = data.config.adsgram_block_id;

            userGreeting.innerText = `أهلاً بيك يا ${data.user.first_name || "بطل"}`;
            userPoints.innerText = currentPoints.toLocaleString();
            userBalance.innerText = currentBalance.toFixed(2);
            userAds.innerText = data.user.total_ads_watched;
            minPointsText.innerText = (minWithdrawal * 100).toLocaleString();
            minWithdrawText.innerText = minWithdrawal.toFixed(0);

            updateAttemptsDisplay();
            initAdsgram();
        } else {
            showAlert("حصلت مشكلة في تحميل بيانات اللعبة: " + (data.error || ""), "error");
        }
    } catch (err) {
        console.error("Error fetching user data:", err);
        showAlert("مش عارفين نوصل للسيرفر، اتأكد من النت عندك.", "error");
    }
}

// تهيئة كود إعلانات Adsgram
function initAdsgram() {
    if (window.Adsgram && adsgramBlockId && adsgramBlockId !== "YOUR_ADSGRAM_BLOCK_ID") {
        try {
            adController = window.Adsgram.init({ blockId: adsgramBlockId });
        } catch (e) {
            console.error("Failed to init Adsgram:", e);
        }
    }
}

// منطق اللعب: الضغط على كروت الحظ
gameCards.forEach(card => {
    card.addEventListener("click", async () => {
        if (card.classList.contains("revealed")) return;

        if (gameAttempts <= 0) {
            showAlert("خلصت كل محاولاتك! اضغط على زرار شحن المحاولات عشان تشحن 3 محاولات جداد وتكمل لعب.", "info");
            return;
        }

        // خصم محاولة
        gameAttempts--;
        updateAttemptsDisplay();

        // كشف الكارت
        card.classList.add("revealed");
        showAlert("عاش! كشفت الكارت بنجاح، اشحن محاولات عشان تضاعف نقاطك!", "success");

        if (tg?.HapticFeedback) {
            tg.HapticFeedback.impactOccurred("medium");
        }

        // إعادة تغطية الكارت بعد ثانيتين ليختاره مجدداً
        setTimeout(() => {
            card.classList.remove("revealed");
        }, 1800);

        if (gameAttempts <= 0) {
            showAlert("خلصت كل محاولات اللعب! اشحن 3 محاولات مجاناً بمشاهدة الفيديو.", "info");
        }
    });
});

// شحن المحاولات بمشاهدة الفيديو (Rewarded Ad)
btnWatchAd.addEventListener("click", async () => {
    btnWatchAd.disabled = true;
    btnWatchAd.querySelector(".btn-text").innerText = "بيجهز الفيديو...";

    // وضع تجريبي إذا لم يكن البلوك جاهزاً
    if (!adController || adsgramBlockId === "YOUR_ADSGRAM_BLOCK_ID") {
        const simulate = confirm("تنبيه: هل تود محاكاة مشاهدة الفيديو لشحن 3 محاولات وإضافة النقاط؟");
        if (simulate) {
            await creditRewardAndRefill();
        } else {
            btnWatchAd.disabled = false;
            updateAttemptsDisplay();
        }
        return;
    }

    // تشغيل الإعلان عبر Adsgram
    adController.show().then(async (result) => {
        showAlert("عاش! شوفت الفيديو كامل، بنشحنلك المحاولات والنقاط...", "info");
        await creditRewardAndRefill();
    }).catch((result) => {
        let msg = "مشوفتش الفيديو للآخر، فالمحاولات متجددتش.";
        if (result && result.description) {
            if (result.description.includes("no ads") || result.description.includes("empty")) {
                msg = "مفيش فيديوهات متاحة حالياً، جرب تاني بعد دقيقة.";
            }
        }
        showAlert(msg, "error");
        btnWatchAd.disabled = false;
        updateAttemptsDisplay();
    });
});

// إرسال تأكيد المكافأة وشحن المحاولات
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
        
        if (data.success) {
            currentBalance = data.new_balance;
            currentPoints = Math.round(currentBalance * 100);
            userBalance.innerText = currentBalance.toFixed(2);
            userPoints.innerText = currentPoints.toLocaleString();
            userAds.innerText = parseInt(userAds.innerText) + 1;

            // شحن 3 محاولات لعب جديدة
            gameAttempts = 3;
            updateAttemptsDisplay();

            showAlert(`مبروك! تم شحن 3 محاولات ونزل في رصيدك +${Math.round(rewardAmount * 100)} نقطة.`, "success");
            
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred("success");
            }
        } else {
            showAlert(data.message || "حصلت مشكلة في شحن المحاولات", "error");
        }
    } catch (err) {
        console.error("Reward error:", err);
        showAlert("فشل تحديث الرصيد، اتأكد من النت عندك.", "error");
    } finally {
        btnWatchAd.disabled = false;
        updateAttemptsDisplay();
    }
}

// معالجة استبدال النقاط وسحب الكاش
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
        showAlert(`أقل حد للاستبدال هو ${minWithdrawal} جنيه (${minWithdrawal * 100} نقطة)`, "error");
        return;
    }

    if (amount > currentBalance) {
        showAlert(`رصيدك الحالي (${currentPoints} نقطة = ${currentBalance.toFixed(2)} ج) ميكفيش تسحب المبلغ ده!`, "error");
        return;
    }

    const confirmWithdraw = confirm(`تأكيد استبدال النقاط:\n\nالمحفظة: ${selectedProvider}\nالرقم: ${phone}\nالمبلغ المطلوب: ${amount} جنيه (${amount * 100} نقطة)\n\nالبيانات كده صح؟`);
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
            showAlert("تم إرسال طلب استبدال النقاط بنجاح، هيتم تحويل الكاش لمحفظتك قريباً.", "success");
            currentBalance -= amount;
            currentPoints = Math.round(currentBalance * 100);
            userBalance.innerText = currentBalance.toFixed(2);
            userPoints.innerText = currentPoints.toLocaleString();
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
        btnSubmit.innerText = "تأكيد استبدال النقاط";
    }
});

// تحميل سجل السحوبات والجوائز
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
                    statusText = "مرفوض والنقاط رجعت لرصيدك";
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
            historyList.innerHTML = '<p class="empty-msg">مفيش أي سحوبات سابقة لحد دلوقتي.</p>';
        }
    } catch (err) {
        historyList.innerHTML = '<p class="empty-msg">فشل تحميل السجل.</p>';
    }
}

// بدء التحميل
loadUserData();
