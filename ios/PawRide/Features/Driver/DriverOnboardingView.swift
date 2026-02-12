import SwiftUI

struct DriverOnboardingView: View {
    @State private var vehicleMake = ""
    @State private var vehicleModel = ""
    @State private var plate = ""
    @State private var hasCrate = true
    @State private var maxDogs = 1

    var body: some View {
        Form {
            Section("Vehicle") {
                TextField("Make", text: $vehicleMake)
                TextField("Model", text: $vehicleModel)
                TextField("Plate", text: $plate)
            }
            Section("Dog Accommodations") {
                Toggle("Crate available", isOn: $hasCrate)
                Stepper("Max dogs: \(maxDogs)", value: $maxDogs, in: 1...4)
            }
            Section("Documents") {
                Button("Upload License") {}
                Button("Upload Insurance") {}
                Button("Upload Registration") {}
                Button("Upload Animal Handling Cert") {}
            }
            Button("Submit for Review") {}
        }
        .navigationTitle("Driver Onboarding")
    }
}
