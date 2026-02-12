import SwiftUI

struct ParentTabView: View {
    var body: some View {
        TabView {
            ParentHomeView()
                .tabItem { Label("Home", systemImage: "house.fill") }
            ParentDogsView()
                .tabItem { Label("My Dogs", systemImage: "pawprint.fill") }
            ParentRidesView()
                .tabItem { Label("Rides", systemImage: "car.fill") }
            ParentPaymentsView()
                .tabItem { Label("Payments", systemImage: "creditcard.fill") }
            ParentSettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}
