import SwiftUI

struct ParentPaymentsView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Payment Methods") {
                    Label("Visa •••• 4242", systemImage: "creditcard")
                    Button("Add New Card") {}
                }
                Section("PawRide Pass") {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("PawRide Pass")
                            .font(.headline)
                        Text("$29.99 / month • 10% ride discount • priority matching")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Button("Subscribe") {}
                }
                Section("Receipts") {
                    Text("Ride receipts will appear here.")
                        .foregroundStyle(.secondary)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Payments")
        }
    }
}
