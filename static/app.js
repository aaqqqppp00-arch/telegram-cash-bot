// تهيئة تليجرام ويب آب
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// عناصر الصفحة
const userGreeting = document.getElementById("user-greeting");
const userBalance = document.getElementById("user-balance");
const userAds = document.getElementById("user-ads");
const rewardRate = document.getElementById("reward-rate");
const minWithdrawText = document.getElementById("min-withdraw-text");
const alertBox = document.getElementById("alert-box");

// الشاشات
const screenHome = document.getElementById("screen-home");
const screenWithdraw = document.getElementById("screen-withdraw");
const screenHistory = document.getElementById("screen-history");

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

// متغيرات الحالة
let currentBalance = 0;
let minWithdrawal = 20;
let rewardAmount = 0.05;
let adsgramBlockId = "";
let adController = null;

// التحقق من وجود initData (داخل تليجرام أو وضع التجربة)
const initData = tg?.initData || "user=" + encodeURIComponent(JSON.stringify({
    id: 999999999,
    first_name: "مستخدم تجريبي",
    username: "test_user"
})) + "&hash=mock";

// إظهار التنبيهات
function showAlert(message, type = "info") {
    alertBox.className = `alert-box ${type}`;
    alertBox.innerText = message;
    alertBox.scrollIntoView({ behavior: "smooth" });
    
    // إخفاء التنبيه بعد 5 ثوانٍ
    setTimeout(() => {
        alertBox.className = "alert-box hidden";
    }, 5000);
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
            minWithdrawal = data.config.min_withdrawal;
            rewardAmount = data.config.reward_per_ad;
            adsgramBlockId = data.config.adsgram_block_id;

            userGreeting.innerText = `أهلاً بك يا ${data.user.first_name || "صديقنا"}`;
            userBalance.innerText = currentBalance.toFixed(2);
            userAds.innerText = data.user.total_ads_watched;
            rewardRate.innerText = `${rewardAmount.toFixed(2)} جنيه`;
            minWithdrawText.innerText = minWithdrawal.toFixed(0);

            // تجهيز متحكم Adsgram
            initAdsgram();
        } else {
            showAlert("حدث خطأ في تحميل بياناتك: " + (data.error || ""), "error");
        }
    } catch (err) {
        console.error("Error fetching user data:", err);
        showAlert("تعذر الاتصال بالسيرفر. تأكد من اتصال الإنترنت.", "error");
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

// تشغيل إعلان Adsgram
btnWatchAd.addEventListener("click", async () => {
    btnWatchAd.disabled = true;
    btnWatchAd.querySelector(".btn-text").innerText = "جاري تجهيز الإعلان...";

    // إذا لم يضبط المشرف معرّف الإعلانات الحقيقي بعد (وضع تجريبي للتأكد من عمل البوت)
    if (!adController || adsgramBlockId === "YOUR_ADSGRAM_BLOCK_ID") {
        const simulate = confirm("تنبيه المشرف: لم يتم وضع كود Adsgram Block ID الحقيقي بعد في الإعدادات.\n\nهل تود محاكاة مشاهدة إعلان تجريبياً لإضافة الرصيد؟");
        if (simulate) {
            await creditReward();
        } else {
            btnWatchAd.disabled = false;
            btnWatchAd.querySelector(".btn-text").innerText = "شاهد إعلان الآن واكسب الفلوس";
        }
        return;
    }

    // تشغيل الإعلان الحقيقي عبر Adsgram
    adController.show().then(async (result) => {
        // المستخدم أنهى الإعلان كاملاً!
        showAlert("أحسنت! لقد شاهدت الإعلان كاملاً، جاري إضافة المكافأة...", "info");
        await creditReward();
    }).catch((result) => {
        // المستخدم أغلق الإعلان أو حدث خطأ في الشبكة
        let msg = "لم تكمل مشاهدة الإعلان حتى نهايته، لم تتم إضافة المكافأة.";
        if (result && result.description) {
            if (result.description.includes("no ads") || result.description.includes("empty")) {
                msg = "لا تتوفر إعلانات جديدة حالياً في منطقتك، جرب مجدداً بعد دقيقة.";
            }
        }
        showAlert(msg, "error");
        btnWatchAd.disabled = false;
        btnWatchAd.querySelector(".btn-text").innerText = "شاهد إعلان الآن واكسب الفلوس";
    });
});

// إرسال طلب إضافة المكافأة للسيرفر
async function creditReward() {
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
            userBalance.innerText = currentBalance.toFixed(2);
            userAds.innerText = parseInt(userAds.innerText) + 1;
            showAlert(`مبروك! تمت إضافة +${rewardAmount.toFixed(2)} جنيه إلى رصيدك.`, "success");
            
            // اهتزاز خفيف للموبايل إن وجد
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred("success");
            }
        } else {
            showAlert(data.message || "حدث خطأ أثناء إضافة الرصيد", "error");
        }
    } catch (err) {
        console.error("Reward error:", err);
        showAlert("فشل إرسال المكافأة، تأكد من الاتصال بالإنترنت.", "error");
    } finally {
        btnWatchAd.disabled = false;
        btnWatchAd.querySelector(".btn-text").innerText = "شاهد إعلان الآن واكسب الفلوس";
    }
}

// معالجة نموذج السحب
withdrawForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const selectedProvider = document.querySelector('input[name="provider"]:checked').value;
    const phone = withdrawPhone.value.trim();
    const amount = parseFloat(withdrawAmount.value);

    // التحقق المبدئي
    if (!phone || phone.length !== 11) {
        showAlert("يجب إدخال رقم هاتف صحيح مكون من 11 رقماً", "error");
        return;
    }

    if (isNaN(amount) || amount < minWithdrawal) {
        showAlert(`الحد الأدنى للسحب هو ${minWithdrawal} جنيه`, "error");
        return;
    }

    if (amount > currentBalance) {
        showAlert(`رصيدك الحالي (${currentBalance.toFixed(2)} ج) غير كافٍ لسحب هذا المبلغ!`, "error");
        return;
    }

    const confirmWithdraw = confirm(`تأكيد السحب:\n\nالمحفظة: ${selectedProvider}\nالرقم: ${phone}\nالمبلغ: ${amount} جنيه\n\nهل البيانات صحيحة؟`);
    if (!confirmWithdraw) return;

    const btnSubmit = document.getElementById("btn-submit-withdraw");
    btnSubmit.disabled = true;
    btnSubmit.innerText = "جاري إرسال الطلب...";

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
            showAlert(data.message, "success");
            currentBalance -= amount;
            userBalance.innerText = currentBalance.toFixed(2);
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
        showAlert("حدث خطأ أثناء التواصل مع السيرفر.", "error");
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerText = "✅ إرسال طلب السحب الآن";
    }
});

// تحميل سجل السحوبات
async function loadWithdrawalHistory() {
    historyList.innerHTML = '<p class="empty-msg">جاري تحميل السجل...</p>';
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
                let statusText = "قيد المراجعة ⏳";
                if (w.status === "approved") {
                    badgeClass = "badge-approved";
                    statusText = "تم التحويل بنجاح ✅";
                } else if (w.status === "rejected") {
                    badgeClass = "badge-rejected";
                    statusText = "مرفوض وتم إرجاع الرصيد ❌";
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
            historyList.innerHTML = '<p class="empty-msg">لا توجد لديك عمليات سحب سابقة حتى الآن.</p>';
        }
    } catch (err) {
        historyList.innerHTML = '<p class="empty-msg">فشل تحميل السجل.</p>';
    }
}

// بدء التحميل
loadUserData();
