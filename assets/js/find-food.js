import {
  collection,
  db,
  doc,
  getDoc,
  getDocs,
  limit,
  query,
  serverTimestamp,
  setDoc,
  Timestamp,
  where
} from "./firebase-client.js";
import { requireRole } from "./page-auth.js";

const listingList = document.getElementById("listing-list");
const requestList = document.getElementById("request-list");
let currentUser;
let currentProfile;

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function formatDate(value) {
  return value?.toDate ? value.toDate().toLocaleString("en-IN") : "Not available";
}

async function loadData() {
  listingList.replaceChildren(makeElement("p", "", "Loading available food..."));
  requestList.replaceChildren(makeElement("p", "", "Loading your requests..."));
  try {
    const [availableSnapshot, requestsSnapshot] = await Promise.all([
      getDocs(query(
        collection(db, "listings"),
        where("status", "==", "available"),
        where("expiresAt", ">", Timestamp.now()),
        limit(50)
      )),
      getDocs(query(collection(db, "requests"), where("requesterUid", "==", currentUser.uid), limit(100)))
    ]);

    const requestedListings = new Set();
    requestsSnapshot.forEach(item => {
      const request = item.data();
      if (request.status === "pending" || request.status === "accepted") requestedListings.add(request.listingId);
    });
    const listings = availableSnapshot.docs
      .map(item => ({ id: item.id, ...item.data() }))
      .sort((a, b) => (a.pickupBy?.toMillis?.() || 0) - (b.pickupBy?.toMillis?.() || 0));
    listingList.replaceChildren();

    if (!listings.length) {
      listingList.append(makeElement("p", "fb-empty-state", "There are no available food listings right now. Check again soon."));
    }

    listings.forEach(item => {
      const card = makeElement("article", "fb-record-card");
      const heading = makeElement("div", "fb-record-heading");
      heading.append(makeElement("h3", "", item.foodName), makeElement("span", "fb-record-status fb-status-available", "available"));
      card.append(heading);
      card.append(makeElement("p", "", `${item.quantity} ${item.unit} · ${item.category}`));
      card.append(makeElement("p", "fb-record-meta", `Pickup area: ${item.pickupArea} · Pickup by ${formatDate(item.pickupBy)}`));
      card.append(makeElement("p", "fb-record-meta", `Use by ${formatDate(item.expiresAt)}`));
      if (item.notes) card.append(makeElement("p", "", item.notes));

      if (item.ownerUid === currentUser.uid) {
        card.append(makeElement("p", "fb-record-meta", "This is your organization's listing."));
      } else if (requestedListings.has(item.id)) {
        card.append(makeElement("p", "fb-record-meta", "You have already requested this listing."));
      } else {
        const requestForm = document.createElement("form");
        requestForm.className = "fb-request-form";
        const label = makeElement("label", "", "Message to the donor");
        const messageInput = document.createElement("textarea");
        messageInput.rows = 2;
        messageInput.maxLength = 500;
        messageInput.required = true;
        messageInput.placeholder = "Tell the donor about your kitchen's need and pickup capacity.";
        const button = makeElement("button", "btn-primary", "Request this food");
        button.type = "submit";
        requestForm.append(label, messageInput, button);
        requestForm.addEventListener("submit", async event => {
          event.preventDefault();
          button.disabled = true;
          try {
            await setDoc(doc(collection(db, "requests")), {
              listingId: item.id,
              foodName: item.foodName,
              requesterUid: currentUser.uid,
              requesterName: currentProfile.displayName,
              donorUid: item.ownerUid,
              message: messageInput.value.trim(),
              status: "pending",
              createdAt: serverTimestamp()
            });
            await loadData();
          } catch (error) {
            console.error("Could not send the food request.", error);
            button.disabled = false;
            const feedback = makeElement("p", "fb-page-status fb-page-status-error", "Your request could not be sent. The listing may no longer be available; refresh and try again.");
            requestForm.append(feedback);
          }
        });
        card.append(requestForm);
      }
      listingList.append(card);
    });

    const requests = requestsSnapshot.docs
      .map(item => ({ id: item.id, ...item.data() }))
      .sort((a, b) => (b.createdAt?.toMillis?.() || 0) - (a.createdAt?.toMillis?.() || 0));
    requestList.replaceChildren();
    if (!requests.length) requestList.append(makeElement("p", "fb-empty-state", "You have not requested any food yet."));
    for (const request of requests) {
      const card = makeElement("article", "fb-record-card");
      let listing = null;
      if (request.status === "accepted") {
        const listingSnapshot = await getDoc(doc(db, "listings", request.listingId));
        listing = listingSnapshot.exists() ? listingSnapshot.data() : null;
      }
      const heading = makeElement("div", "fb-record-heading");
      heading.append(
        makeElement("h3", "", request.foodName || listing?.foodName || "Food listing"),
        makeElement("span", `fb-record-status fb-status-${request.status}`, request.status)
      );
      card.append(heading, makeElement("p", "", request.message));
      if (request.status === "accepted" && listing?.deliveryTaskId) {
        const privateSnapshot = await getDoc(doc(db, "listingPrivate", request.listingId));
        if (privateSnapshot.exists()) {
          const privateDetails = privateSnapshot.data();
          card.append(makeElement("p", "fb-record-subheading", "Pickup details"));
          card.append(makeElement("p", "", privateDetails.pickupAddress));
          card.append(makeElement("p", "", `Donor phone: ${privateDetails.contactPhone}`));
        }
        const taskSnapshot = await getDoc(doc(db, "deliveryTasks", listing.deliveryTaskId));
        card.append(makeElement(
          "p",
          "fb-record-meta",
          taskSnapshot.exists()
            ? `Delivery status: ${taskSnapshot.data().status}.`
            : "The donor accepted your request."
        ));
      }
      requestList.append(card);
    }
  } catch (error) {
    console.error("Could not load community kitchen listings or requests.", error);
    listingList.replaceChildren(makeElement("p", "fb-page-status fb-page-status-error", "Could not load available food. Check your connection and refresh."));
    requestList.replaceChildren(makeElement("p", "fb-page-status fb-page-status-error", "Could not load your requests."));
  }
}

requireRole(["kitchen"], ({ user, profile }) => {
  currentUser = user;
  currentProfile = profile;
  loadData();
});

document.getElementById("refresh-listings").addEventListener("click", loadData);
