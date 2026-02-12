import SwiftUI

struct DriverEarningsView: View {
    @EnvironmentObject private var authStore: AuthStore
    @StateObject private var store = DriverStore()

    var body: some View {
        NavigationStack {
            List {
                Section("Summary") {
                    HStack {
                        Text("Total Earnings")
                        Spacer()
                        Text(String(format: "$%.2f", store.earningsSummary["total_earnings"] ?? 0))
                            .font(.headline)
                    }
                    HStack {
                        Text("Tips")
                        Spacer()
                        Text(String(format: "$%.2f", store.earningsSummary["tips_total"] ?? 0))
                    }
                    HStack {
                        Text("Rides")
                        Spacer()
                        Text(String(format: "%.0f", store.earningsSummary["ride_count"] ?? 0))
                    }
                }
                Section("Payouts") {
                    Text("Weekly and instant payout history is available via backend endpoint /payments/payouts/me")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Earnings")
            .task {
                guard let token = authStore.accessToken else { return }
                await store.refresh(accessToken: token)
            }
        }
    }
}
