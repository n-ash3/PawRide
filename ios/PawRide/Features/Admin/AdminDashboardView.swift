import SwiftUI

struct AdminDashboardView: View {
    @EnvironmentObject private var authStore: AuthStore
    @StateObject private var store = AdminStore()

    var body: some View {
        NavigationStack {
            List {
                Section("Today") {
                    metricRow("Active Rides", value: store.overview["active_rides"] ?? 0)
                    metricRow("Completed Rides", value: store.overview["completed_rides"] ?? 0)
                    metricRow("Revenue", value: store.overview["total_revenue"] ?? 0, prefix: "$")
                    metricRow("New Signups", value: store.overview["new_signups"] ?? 0)
                }
                if let errorMessage = store.errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Admin Dashboard")
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

    private func metricRow(_ title: String, value: Double, prefix: String = "") -> some View {
        HStack {
            Text(title)
            Spacer()
            if prefix.isEmpty {
                Text(String(format: "%.0f", value))
            } else {
                Text("\(prefix)\(String(format: "%.2f", value))")
            }
        }
    }
}
