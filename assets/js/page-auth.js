import {
  auth,
  db,
  doc,
  firebaseConfigured,
  getDoc,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence
} from "./firebase-client.js";

export function setPageMessage(message, type = "info") {
  const status = document.getElementById("page-status");
  status.textContent = message;
  status.className = `fb-page-status fb-page-status-${type}`;
  status.hidden = !message;
}

export function showPageContent() {
  document.getElementById("page-content").hidden = false;
  document.getElementById("page-status").hidden = true;
}

function watchSession(roles, onReady, allowPending) {
  if (!firebaseConfigured || !auth || !db) {
    setPageMessage("Account services are not configured. Contact the site administrator.", "error");
    return;
  }

  setPersistence(auth, browserLocalPersistence).then(() => {
    onAuthStateChanged(auth, async user => {
      if (!user) {
        const next = encodeURIComponent(window.location.pathname.split("/").pop());
        window.location.replace(`login.html?next=${next}`);
        return;
      }
      try {
        const profileSnapshot = await getDoc(doc(db, "profiles", user.uid));
        if (!profileSnapshot.exists()) {
          setPageMessage("Your account profile is not ready. Contact the FoodBridge administrator.", "error");
          return;
        }
        const profile = profileSnapshot.data();
        if (!allowPending && (profile.approvalStatus !== "approved" || profile.role === "pending")) {
          setPageMessage("Your account is waiting for FoodBridge role approval. You can check its status under My account.", "info");
          return;
        }
        if (!allowPending && !roles.includes(profile.role)) {
          setPageMessage("This workspace is for a different FoodBridge role. Open My account to see your approved role.", "error");
          return;
        }
        showPageContent();
        onReady({ user, profile });
      } catch (error) {
        console.error("Could not verify the FoodBridge account role.", error);
        setPageMessage("Could not verify your account. Check your connection and try again.", "error");
      }
    }, error => {
      console.error("Could not observe the FoodBridge account session.", error);
      setPageMessage("Could not verify your sign-in. Please log in again.", "error");
    });
  }).catch(error => {
    console.error("Could not initialize the FoodBridge account session.", error);
    setPageMessage("Could not initialize account services. Check your connection and try again.", "error");
  });
}

export function requireRole(roles, onReady) {
  watchSession(roles, onReady, false);
}

export function requireAccount(onReady) {
  watchSession([], onReady, true);
}
