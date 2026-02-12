import SwiftUI

struct DriverHomeView: View {
    @EnvironmentObject private var authStore: AuthStore
    @StateObject private var store = DriverStore()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Toggle(isOn: Binding(
                        get: { store.isOnline },
                        set: { newValue in
                            guard let token = authStore.accessToken else { return }
                            Task { await store.setOnline(newValue, accessToken: token) }
                        }
                    )) {
                        Text("Driver Online")
                            .font(.headline)
                    }
                    .padding()
                    .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 14))

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Incoming Ride Offers")
                            .font(.headline)
                        if store.offers.isEmpty {
                            Text("No open offers right now.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(store.offers) { offer in
                                VStack(alignment: .leading, spacing: 6) {
                                    Text("Ride \(offer.rideID.prefix(8)) • \(offer.distanceKM, specifier: "%.1f") km")
                                    Text("Expires: \(offer.expiresAt)")
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                    Button("Accept Offer") {
                                        guard let token = authStore.accessToken else { return }
                                        Task { await store.acceptOffer(offer, accessToken: token) }
                                    }
                                    .buttonStyle(.borderedProminent)
                                }
                                .padding()
                                .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 12))
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                    if let errorMessage = store.errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                }
                .padding()
            }
            .background(PawRideTheme.background)
            .navigationTitle("Driver Home")
            .task {
                guard let token = authStore.accessToken else { return }
                await store.refresh(accessToken: token)
            }
            .refreshable {
                guard let token = authStore.accessToken else { return }
                await store.refresh(accessToken: token)
            }
        }
    }
}
