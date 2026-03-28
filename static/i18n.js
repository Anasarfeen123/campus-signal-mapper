// static/i18n.js — English & Tamil translations
"use strict";

const I18N = {
    en: {
        // Nav
        "nav.map":         "Map",
        "nav.contribute":  "Contribute",
        "nav.leaderboard": "Leaderboard",
        "nav.buildings":   "Buildings",

        // Index page
        "brand.name":      "Signal Map",
        "brand.sub":       "VIT Chennai · Live",
        "stat.samples":    "Samples",
        "stat.avg_dbm":    "Avg dBm",
        "stat.avg_mbps":   "Avg Mbps",
        "layer.label":     "// Data Layer",
        "layer.signal":    "Signal Strength (dBm)",
        "layer.speed":     "Download Speed (Mbps)",
        "carrier.label":   "// Carrier",
        "carrier.all":     "All Carriers",
        "network.label":   "// Network",
        "network.all":     "All Types",
        "btn.locate":      "📍 Locate Me",
        "btn.contribute":  "＋ Contribute Data",
        "btn.offline_map": "🗺️ Download Offline Map",
        "offline.msg":     "// OFFLINE — UPDATES PAUSED",
        "chart.title":     "// Signal History (7 days)",
        "chart.signal":    "Signal Strength",
        "chart.speed":     "Download Speed",

        // Upload page
        "upload.title":    "Contribute",
        "upload.sub":      "Submit mobile coverage data for campus signal mapping",
        "upload.info1":    "📍 Location used only to verify campus presence",
        "upload.info2":    "🔒 No personal data is stored or transmitted",
        "carrier.select":  "Select carrier…",
        "carrier.detect":  "⬡ AUTO-DETECT MY CARRIER",
        "network.type":    "// Network Type",
        "network.auto":    "Auto-detect (recommended)",
        "signal.label":    "// Signal Strength (dBm) — optional",
        "signal.hint":     "HOW TO FIND ON ANDROID",
        "btn.submit":      "Get Location & Submit",
        "back.map":        "← Back to Map",

        // Leaderboard
        "lb.title":        "Leaderboard",
        "lb.sub":          "Top contributors this session",
        "lb.rank":         "Rank",
        "lb.id":           "Contributor",
        "lb.subs":         "Submissions",
        "lb.signal":       "Avg Signal",
        "lb.speed":        "Avg Speed",
        "lb.last":         "Last Active",
        "lb.empty":        "No contributions yet. Be the first!",

        // Buildings
        "bld.title":       "Building Report",
        "bld.sub":         "Per-building signal quality across campus",
        "bld.coverage":    "Campus Coverage",
        "bld.samples":     "samples",
        "bld.no_data":     "No data",
        "quality.excellent": "Excellent",
        "quality.good":    "Good",
        "quality.fair":    "Fair",
        "quality.poor":    "Poor",
        "quality.none":    "No Data",

        // Admin
        "admin.title":     "Admin Dashboard",
        "admin.logout":    "Logout",
        "admin.export":    "Export CSV",
        "admin.clear":     "Clear All Data",
        "admin.delete":    "Delete",
        "admin.confirm_clear": "Type DELETE_ALL to confirm wiping all data",
    },

    ta: {
        // Nav
        "nav.map":         "வரைபடம்",
        "nav.contribute":  "பங்களிக்கவும்",
        "nav.leaderboard": "தரவரிசை",
        "nav.buildings":   "கட்டிடங்கள்",

        // Index page
        "brand.name":      "சிக்னல் வரைபடம்",
        "brand.sub":       "VIT சென்னை · நேரலை",
        "stat.samples":    "மாதிரிகள்",
        "stat.avg_dbm":    "சராசரி dBm",
        "stat.avg_mbps":   "சராசரி Mbps",
        "layer.label":     "// தரவு அடுக்கு",
        "layer.signal":    "சிக்னல் வலிமை (dBm)",
        "layer.speed":     "பதிவிறக்க வேகம் (Mbps)",
        "carrier.label":   "// சேவையகம்",
        "carrier.all":     "அனைத்து சேவையகங்கள்",
        "network.label":   "// நெட்வொர்க்",
        "network.all":     "அனைத்து வகைகள்",
        "btn.locate":      "📍 என் இடம்",
        "btn.contribute":  "＋ தரவு சேர்க்கவும்",
        "btn.offline_map": "🗺️ ஆஃப்லைன் வரைபடம்",
        "offline.msg":     "// இணைப்பு இல்லை — நிறுத்தப்பட்டது",
        "chart.title":     "// சிக்னல் வரலாறு (7 நாட்கள்)",
        "chart.signal":    "சிக்னல் வலிமை",
        "chart.speed":     "பதிவிறக்க வேகம்",

        // Upload page
        "upload.title":    "பங்களிக்கவும்",
        "upload.sub":      "கேம்பஸ் சிக்னல் வரைபடத்திற்கு தரவு சமர்பிக்கவும்",
        "upload.info1":    "📍 இடம் கேம்பஸை சரிபார்க்க மட்டுமே பயன்படுத்தப்படுகிறது",
        "upload.info2":    "🔒 தனிப்பட்ட தரவு சேமிக்கப்படவில்லை",
        "carrier.select":  "சேவையகம் தேர்ந்தெடுக்கவும்…",
        "carrier.detect":  "⬡ சேவையகத்தை கண்டறிக",
        "network.type":    "// நெட்வொர்க் வகை",
        "network.auto":    "தானாக கண்டறி (பரிந்துரைக்கப்படுகிறது)",
        "signal.label":    "// சிக்னல் வலிமை (dBm) — விரும்பினால்",
        "signal.hint":     "ஆண்ட்ராய்டில் எப்படி காண்பது",
        "btn.submit":      "இடம் பெற்று சமர்பிக்கவும்",
        "back.map":        "← வரைபடத்திற்கு திரும்பு",

        // Leaderboard
        "lb.title":        "தரவரிசை",
        "lb.sub":          "சிறந்த பங்களிப்பாளர்கள்",
        "lb.rank":         "வரிசை",
        "lb.id":           "பங்களிப்பாளர்",
        "lb.subs":         "சமர்பிப்புகள்",
        "lb.signal":       "சராசரி சிக்னல்",
        "lb.speed":        "சராசரி வேகம்",
        "lb.last":         "கடைசி செயல்பாடு",
        "lb.empty":        "இன்னும் பங்களிப்பு இல்லை. முதலாவது ஆகுங்கள்!",

        // Buildings
        "bld.title":       "கட்டிட அறிக்கை",
        "bld.sub":         "கேம்பஸ் முழுவதும் கட்டிட வாரியான சிக்னல் தரம்",
        "bld.coverage":    "கேம்பஸ் கவரேஜ்",
        "bld.samples":     "மாதிரிகள்",
        "bld.no_data":     "தரவு இல்லை",
        "quality.excellent": "மிகவும் நல்லது",
        "quality.good":    "நல்லது",
        "quality.fair":    "சரியானது",
        "quality.poor":    "மோசம்",
        "quality.none":    "தரவு இல்லை",

        // Admin (keep in English for admin panel)
        "admin.title":     "Admin Dashboard",
        "admin.logout":    "Logout",
        "admin.export":    "Export CSV",
        "admin.clear":     "Clear All Data",
        "admin.delete":    "Delete",
        "admin.confirm_clear": "Type DELETE_ALL to confirm wiping all data",
    }
};

// -------------------------------------------------
// i18n engine
// -------------------------------------------------

let _currentLang = localStorage.getItem("vit_lang") || "en";

function t(key) {
    return (I18N[_currentLang] && I18N[_currentLang][key]) ||
           (I18N["en"] && I18N["en"][key]) ||
           key;
}

function applyTranslations() {
    document.documentElement.lang = _currentLang === "ta" ? "ta" : "en";
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        const val = t(key);
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
            el.placeholder = val;
        } else if (el.tagName === "OPTION") {
            el.textContent = val;
        } else {
            el.textContent = val;
        }
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(el => {
        el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
}

function setLang(lang) {
    _currentLang = lang;
    localStorage.setItem("vit_lang", lang);
    applyTranslations();
    // notify other modules
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
}

function currentLang() { return _currentLang; }

// Apply on load
document.addEventListener("DOMContentLoaded", applyTranslations);