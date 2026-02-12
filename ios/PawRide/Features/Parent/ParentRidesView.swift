import SwiftUI

struct ParentRidesView: View {
    @EnvironmentObject private var authStore: AuthStore
    @State private var rides: [Ride] = []
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            List {
                ForEach(rides) { ride in
                    NavigationLink {
                        ParentRideTrackingView(ride: ride)
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(ride.pickupAddress) → \(ride.dropoffAddress)")
                                .font(.headline)
                            Text("Status: \(ride.status)")
                                .foregroundStyle(.secondary)
                            Text(String(format: "$%.2f", ride.fareTotal))
                                .font(.footnote.monospacedDigit())
                        }
                        .padding(.vertical, 4)
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Ride History")
            .task { await loadRides() }
            .refreshable { await loadRides() }
        }
    }

    private func loadRides() async {
        guard let token = authStore.accessToken else { return }
        do {
            rides = try await APIClient.shared.fetchRides(accessToken: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
