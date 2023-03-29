# print("Loaded pi-control init")

from inspect import ismethod


def is_method(instance, method):
	if hasattr(instance, method) and ismethod(getattr(instance, method)):
		return True
	return False

