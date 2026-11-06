import {
  auth,
  db,
  doc,
  serverTimestamp,
  updateDoc,
  updateProfile
} from "./firebase-client.js";
import { requireAccount as requireSignedInAccount, setPageMessage } from "./page-auth.js";

const profileForm = document.getElementById("profile-form");
const profileMessage = document.getElementById("profile-message");
const roleLabels = {
  donor: "Food donor / kitchen",
  kitchen: "Community kitchen / recipient",
  volunteer: "Volunteer",
  pending: "Awaiting role approval"
};
let currentProfile;

function showProfileMessage(message, type = "info") {
  profileMessage.textContent = message;
  profileMessage.className = `fb-page-status fb-page-status-${type}`;
  profileMessage.hidden = !message;
}

requireSignedInAccount(({ user, profile }) => {
  currentProfile = profile;
  document.getElementById("profile-name").value = profile.displayName || user.displayName || "";
  document.getElementById("profile-email").value = user.email || "";
  document.getElementById("profile-role").value = roleLabels[profile.requestedRole] || roleLabels.pending;

  const status = document.getElementById("account-status");
  if (profile.approvalStatus === "approved") {
    status.textContent = `Your ${roleLabels[profile.role] || "FoodBridge"} account is approved.`;
    status.className = "fb-account-status fb-account-status-approved";
  } else {
    status.textContent = `Your ${roleLabels[profile.requestedRole] || "FoodBridge"} account is awaiting administrator approval.`;
    status.className = "fb-account-status fb-account-status-pending";
  }
});

profileForm.addEventListener("submit", async event => {
  event.preventDefault();
  showProfileMessage("");
  const displayName = document.getElementById("profile-name").value.trim();
  const button = document.getElementById("save-profile");
  button.disabled = true;
  try {
    await updateProfile(auth.currentUser, { displayName });
    await updateDoc(doc(db, "profiles", auth.currentUser.uid), {
      displayName,
      updatedAt: serverTimestamp()
    });
    if (currentProfile) currentProfile.displayName = displayName;
    showProfileMessage("Your name has been updated.");
  } catch (error) {
    console.error("Could not update the FoodBridge account profile.", error);
    showProfileMessage("Your profile could not be updated. Check your connection and try again.", "error");
  } finally {
    button.disabled = false;
  }
});
