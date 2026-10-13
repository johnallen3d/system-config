# Historical #771 packaging postimage

`production-module.nix` is the exact immutable module from the reviewed #771
packaging-adoption generation:

- Generation: `/nix/store/aqchfhc9p11n1f30m6msjz5dx83k06gq-home-manager-generation`
- Original asset: `/nix/store/r85bjkfjav2hbrn5gdgp4ih8f2d41g8w-source/modules/home-manager/hermes-native/production-module.nix`
- SHA-256: `832fa5e1d15ca7a1cfefb172cf5667e36e14cf234d725fd90741cb6102b8f574`

It is synthetic-test input, not a deployment configuration or new approval.
Lifecycle/adoption tests must not substitute the current module for this
historical postimage: subsequent calendar/task deployments changed the module,
while the one-time approval gate deliberately retains its original hash.

The fixture is outside the runtime fileset and does not change the live identity.
