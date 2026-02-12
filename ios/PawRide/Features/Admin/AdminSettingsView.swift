import SwiftUI

struct AdminSettingsView: View {
    var body: some View {
        NavigationStack {
            RoleSettingsPanel()
                .navigationTitle("Settings")
        }
    }
}
