import SwiftUI

struct ParentHomeView: View {
    @EnvironmentObject private var authStore: AuthStore
    @StateObject private var store = ParentStore()
    @State private var selectedDogID: String = ""
    @State private var pickupAddress = ""
    @State private var dropoffAddress = ""
    @State private var dropoffType = "daycare"

    private var activeRide: Ride? {
        store.rides.first { !["completed", "cancelled"].contains($0.status) }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    RoundedRectangle(cornerRadius: 20)
                        .fill(PawRideTheme.accent.opacity(0.25))
                        .frame(height: 180)
                        .overlay(
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Live Ride Map")
                                    .font(.headline)
                                Text("MapKit integration point")
                                    .foregroundStyle(.secondary)
                            }
                            .padding()
                        )

                    if let activeRide {
                        NavigationLink {
                            ParentRideTrackingView(ride: activeRide)
                        } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("Active Ride")
                                    .font(.headline)
                                Text("Status: \(activeRide.status)")
                                Text("Tap to watch live camera + track route")
                                    .font(.footnote)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(Color.green.opacity(0.15), in: RoundedRectangle(cornerRadius: 14))
                        }
                        .buttonStyle(.plain)
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Book a Ride")
                            .font(.headline)
                        Picker("Dog", selection: $selectedDogID) {
                            ForEach(store.dogs) { dog in
                                Text(dog.name).tag(dog.id)
                            }
                        }
                        .pickerStyle(.menu)
                        TextField("Pickup address", text: $pickupAddress)
                            .textFieldStyle(.roundedBorder)
                        TextField("Dropoff address", text: $dropoffAddress)
                            .textFieldStyle(.roundedBorder)
                        Picker("Dropoff Type", selection: $dropoffType) {
                            Text("Daycare").tag("daycare")
                            Text("Groomer").tag("groomer")
                            Text("Vet").tag("vet")
                            Text("Trusted Person").tag("trusted_person")
                        }
                        .pickerStyle(.segmented)
                        Button {
                            guard let token = authStore.accessToken else { return }
                            Task {
                                await store.requestRide(
                                    dogID: selectedDogID,
                                    pickupAddress: pickupAddress,
                                    dropoffAddress: dropoffAddress,
                                    dropoffType: dropoffType,
                                    accessToken: token
                                )
                            }
                        } label: {
                            Text("Confirm & Request Ride")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(selectedDogID.isEmpty || pickupAddress.isEmpty || dropoffAddress.isEmpty)
                    }
                    .padding()
                    .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 16))

                    if let errorMessage = store.errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                }
                .padding()
            }
            .background(PawRideTheme.background)
            .navigationTitle("PawRide")
            .task {
                guard let token = authStore.accessToken else { return }
                await store.refresh(accessToken: token)
                selectedDogID = store.dogs.first?.id ?? ""
            }
            .refreshable {
                guard let token = authStore.accessToken else { return }
                await store.refresh(accessToken: token)
            }
        }
    }
}
