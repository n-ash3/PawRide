import SwiftUI

struct DriverSettingsView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Driver") {
                    NavigationLink("Driver Onboarding / Profile") {
                        DriverOnboardingView()
                    }
                }
                Section("Account") {
                    NavigationLink("Role & Account Settings") {
                        RoleSettingsPanel()
                            .navigationTitle("Account")
                    }
                }
            }
            .navigationTitle("Settings")
        }
    }
}
