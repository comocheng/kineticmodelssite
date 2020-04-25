#!/usr/bin/env python
# encoding: utf-8
"""
Prime.py

Reads in BURCAT_THR.xml and a PrIMe data warehouse, and compares the two.
Uses a local mirror of the prime warehouse stored in the folder called ./warehouse.primekinetics.org/

Created by Richard West on 2009-06-09.
Copyright (c) 2009 MIT. All rights reserved.
"""

import sys
import os
import unittest
import re
import xml, xml.dom.minidom
import pickle as pickle # try import pickle if that doesn't work
import numpy


class ThingWithCache:
	""" 
	A parent class for things with caches. 
	Classes inheriting from this can use various cache load/save functions.
	This is done to speed up creation of items that take a long time to generate"""
	def loadCache(self):
		"""loads the cache (everything in the list self.cacheItems is attempted)"""
		try:
			for item in self.cacheItems:
				self.loadItem(item)
		except:
			print("couldn't load cache")
			return False
		return True
	def saveCache(self):
		"""Saves the cache (everything in the list self.cacheItems gets saved)"""
		os.path.isdir(self.cacheLocation) or os.makedirs(self.cacheLocation) # check the cache folder exists
		try:
			for item in self.cacheItems:
				self.saveItem(item)
		except:
			print("Couldn't save cache")
			return False
		return True
	def saveItem(self,itemName):
		"""save an item in the cache at self.cacheLocation"""
		obj=getattr(self,itemName)
		filePath=os.path.join(self.cacheLocation,itemName+'.pkl')
		pickle.dump(obj, file(filePath, 'wb'))
	def loadItem(self,itemName):
		"""load an item from the cache in self.cacheLocation,
		   and load it into self.<item>"""
		filePath=os.path.join(self.cacheLocation,itemName+'.pkl')
		setattr(self,itemName,pickle.load(file(filePath, 'rb')))
		
class PrimeSpeciesList(ThingWithCache): # inherit from the parent class ThingWithCache so that we can use the cache load/save functions 
	"""
	This is the class for the main list of Prime Species. 
	All it is really used for is translating between CAS numbers and PrIMe species IDs. 
	Instances of this class (you'll probably only have one such instance) have dictionaries to do this translation.
	If you update your prime mirror then you should delete the cache folder so you regenerate the dictionaries.
	"""
	def __init__(self,mirror="warehouse.primekinetics.org",cache="cache"):
		""" 
		  p=PrimeSpeciesList(mirror="warehouse.primekinetics.org",cache="cache") 
		creates an instance using a local mirror of the prime warehouse stored in the 
		local folder called ./warehouse.primekinetics.org/ (relative to the working folder)
		and a cache stored in the folder ./cache/"""
		self.mirrorLocation=mirror
		self.cacheLocation=cache
		self.cas2primeids=dict()
		self.primeid2cas=dict()
	
		self.cacheItems=['cas2primeids','primeid2cas'] # these are the items we wish to save/load in the cache
		try: 
			self.loadCache() # try to load the cache
		except:
			print("Couldn't load cache.")
			self.readCAS()
			self.saveCache()
		
	def readCAS(self):
		"""
		Reads in the CAS number from every species file in the prime warehouse
		populates the dictionaries self.cas2primeids (notice this is plural - it stores lists of prime ids) 
		                       and self.primeid2cas 
		"""
		path=os.path.join(self.mirrorLocation,'depository','species','catalog')
		listOfFiles=os.listdir(path)
		reCas=re.compile('CASRegistryNumber">([0-9/-]+)</name>')
		for filename in listOfFiles:
			filePath=os.path.join(path,filename)
			if not os.path.isfile(filePath): continue
			data=file(filePath,'r').read()
			match=reCas.search(data)
			primeid=os.path.splitext(filename)[0]
			if match:
				cas=match.group(1)
				print(primeid,cas)
				# each primed has a unique cas so we just store it
				self.primeid2cas[primeid]=cas
				# each cas may have more than one primeid so we store as a list and append
				if cas in self.cas2primeids:
					self.cas2primeids[cas].append(primeid)
					print("Warning! species %s all have same CAS %s"%(self.cas2primeids[cas], cas))
				else:
					self.cas2primeids[cas]=[primeid]
				
class BurcatThermo:
	"""a class for the Burcat Thermodynamics. 
	When you create an instance of this class it reads the BURCAT_THR.xml file into memory, eg.
	   b = BurcatThermo()   or if you prefer:  b=BurcatThermo(mirror='BURCAT_THR.xml') 
	then you can get all the species in the file using
	   for species in b.species():
	"""
	def __init__(self,mirror="BURCAT_THR.xml"):
		# can't cache the dom because pickle's maximum recursion depth is exceeded by the dom.
		self.dom = self.readXML(mirror)
	def __del__(self):
		"""please try to explicitly delete instances of this class, so that the dom is unlinked
		otherwise you get massive amounts of wasted (leaked) memory."""
		self.dom.unlink()

	def readXML(self,mirror):
		""" reads in the XML from the file"""
		print("Reading in %s ..."%mirror)
		dom=xml.dom.minidom.parse(mirror)
		print("Done!")
		return dom
			
	def species(self):
		"""a generator function. returns (one at a time) each species in the Burcat thermo"""
		for specie in self.dom.getElementsByTagName('specie'):
			yield BurcatSpecies(specie)
			
class BurcatSpecies:
	def __init__(self,dom):
		self.dom=dom
		if 'CAS' in self.dom.attributes:
			self.cas=self.dom.attributes.getNamedItem('CAS').value
		else: self.cas="No_CAS_in_Burcat"
	def phases(self):
		for phase in self.dom.getElementsByTagName('phase'):
			if len(phase.childNodes) > 1: # BURCAT_THR.xml has two types of <phase> node. One contains nested child nodes, the other just a text node "S|L|G". We only want the former.
				yield BurcatPhase(phase)
			#else: print "I think %s is not a real phase"%phase.toxml()
			
class BurcatPhase:
	def __init__(self,dom):
		self.dom=dom
	def __str__(self):
		return "%s (%s)"%(self.formula(),self.phaseOfMatter())
	def formula(self):
		formulas= self.dom.getElementsByTagName('formula')
		assert len(formulas)==1 ,"there should be only one formula in this phase"
		return formulas[0].firstChild.wholeText
	def phaseOfMatter(self):
		phases= self.dom.getElementsByTagName('phase')
		assert len(phases)==1 ,"there should be only one phase in this phase"
		return phases[0].firstChild.wholeText
	def coefficients(self):
		""" returns numpy.array([lowTcoeffs, highTcoeffs])  of the thermo polynomial coefficients"""
		coefficientsets=self.dom.getElementsByTagName('coefficients')
		assert len(coefficientsets)==1, "there should only be one set of coefficients"
		coeffs=coefficientsets[0]
		highTcoeffNodes=coeffs.getElementsByTagName('range_1000_to_Tmax')[0].getElementsByTagName('coef')
		lowTcoeffNodes=coeffs.getElementsByTagName('range_Tmin_to_1000')[0].getElementsByTagName('coef')
		highTcoeffs=[]
		for coef in highTcoeffNodes:
			name=coef.getAttribute('name')
			value=float(coef.firstChild.data.replace(' ','').replace('D','E'))
			highTcoeffs.append(value)
		lowTcoeffs=[]
		for coef in lowTcoeffNodes:
			name=coef.getAttribute('name')
			value=float(coef.firstChild.data.replace(' ','').replace('D','E'))
			lowTcoeffs.append(value)
		allCoeffs=numpy.array([lowTcoeffs, highTcoeffs])
		return allCoeffs
		
			
class PrimeSpecies:
	""" a species from the Prime warehouse """
	def __init__(self,primeid,mirror="warehouse.primekinetics.org"):
		self.primeid=primeid
		self.mirrorLocation=mirror
	def thermos(self):
		""" a generator that returns the thermodymnamic polynomials of the species, one at a time, as PrimeThermo objects """
		path=os.path.join(self.mirrorLocation,'depository','species','data',self.primeid)
		if not os.path.exists(path): 
			# print "%s has no thermo polynomials"%self.primeid
			raise StopIteration
		listOfFiles=os.listdir(path)
		# print "%s has thermos %s"%(self.primeid,listOfFiles)
		for filename in listOfFiles:
			filePath=os.path.join(path,filename)
			if not os.path.isfile(filePath): continue
			if not re.match('thp\d+\.xml',filename): continue
			if not int(re.match('thp(\d+).xml',filename).group(1))>0: continue
			try:
				dom=xml.dom.minidom.parse(filePath)
			except xml.parsers.expat.ExpatError as error:
				print("BAD XML IN FILE %s"%filePath)
				print("Error: ",error)
				continue # try next file
			yield PrimeThermo(dom)
			
class PrimeThermo:
	""" a themodynamic polynomial set from the Prime warehouse"""
	def __init__(self,dom):
		self.dom = dom
		self.primeID=dom.firstChild.getAttribute('primeID')
	def __del__(self):
		self.dom.unlink()
	def __str__(self):
		return self.primeID
	def isFromBurcat(self, BurcatBibliographyID='b00014727'):
		""" returns True if one of the bibliographyLink items matches that of Burcat A., Ruscic B., 2006. (b00014727)
			otherwise returns False"""
		for bibItem in self.dom.getElementsByTagName('bibliographyLink'):
			if bibItem.getAttribute('primeID')==BurcatBibliographyID:
				return True
		# we haven't yet returned True and have run out of bibItems...
		return False
		
	def coefficients(self):
		""" returns numpy.array([lowTcoeffs, highTcoeffs])  of the thermo polynomial coefficients"""
		polynomials=self.dom.getElementsByTagName('polynomial')
		assert len(polynomials)==2, "Was expecitng two sets of coefficients"
		# I'm assuming the low T comes first. 
		assert (float(polynomials[0].getElementsByTagName('bound')[0].firstChild.data) < 
		       float(polynomials[1].getElementsByTagName('bound')[0].firstChild.data) ) # check ordering assumption
		highTcoeffNodes=polynomials[1].getElementsByTagName('coefficient')
		lowTcoeffNodes=polynomials[0].getElementsByTagName('coefficient')
		highTcoeffs=[]
		for coef in highTcoeffNodes:
			name=coef.getAttribute('label')
			value=float(coef.firstChild.data)
			highTcoeffs.append(value)
		lowTcoeffs=[]
		for coef in lowTcoeffNodes:
			name=coef.getAttribute('label')
			value=float(coef.firstChild.data)
			lowTcoeffs.append(value)
		allCoeffs=numpy.array([lowTcoeffs, highTcoeffs])
		return allCoeffs
		

#class untitledTests(unittest.TestCase):
#	def setUp(self):
#		pass

if __name__ == '__main__':
#	unittest.main()
	numpy.set_printoptions(precision=1)
	
	
	passList=[]
	failList=[]
	errorList=[]
	notFoundList=[]
	
	p=PrimeSpeciesList()
	
	b=BurcatThermo()

	for specie in b.species():
		print() 
		print("Trying Burcat species with CAS %s"%specie.cas)
		try:
			primeids=p.cas2primeids[specie.cas]
		except KeyError:
			print("Species with CAS %s not found in prime"%specie.cas)
			notFoundList.append(specie.cas)
			continue
			
		for phase in specie.phases():
			print("Looking for Burcat phase %s"%str(phase))
			
			burcatCoeffs = phase.coefficients()
					
			for primeid in primeids:
				print("Trying PrIMe species %s"%primeid)
				primeSpecies=PrimeSpecies(primeid)
				for primeThermo in primeSpecies.thermos():
					if not primeThermo.isFromBurcat():
						print("PrIMe polynomial %s/%s is not from Burcat & Ruscic so skipping comparison"%(primeid,str(primeThermo)))
						continue
					else:
						print("PrIMe polynomial %s/%s claims to be from Burcat & Ruscic"%(primeid,str(primeThermo)))
						try:
							primeCoeffs = primeThermo.coefficients()
						except AssertionError as error:
							print("ERROR reading prime coeffs:",error)
							errorList.append("%s/%s"%(primeid,str(primeThermo)))
							continue
					
						differences = burcatCoeffs - primeCoeffs  # perhaps absolute difference is silly - some coefficients are very small, some are large. finding relative difference leads to divide-by-zero NaN though...
						sumSquareError = numpy.sum(differences*differences )
						print("sum of squared errors = %g"%sumSquareError)
						
						if sumSquareError>1E-3: # arbitrary and probably inappropriate
							print("PrIMe")
							print(primeCoeffs)
							print("Burcat")
							print(burcatCoeffs)
							print("Differences")
							print(differences)
							failList.append("%s/%s"%(primeid,str(primeThermo)))
						else:
							print("seemed to match pass OK")
							passList.append("%s/%s"%(primeid,str(primeThermo)))
							
	print("\n\n******************\n")	
	print("PASSED OK %d POLYNOMIALS"%len(passList))
	for s in passList:
		print(s)
		
	print("\n\n******************\n")
	print("FAILED COMPARISON TEST %d polynomials"%len(failList))
	for s in failList:
		print(s)
	
	print("\n\n******************\n")
	print("ERRORS READING %d PrIMe polynomials"%len(errorList))
	for s in errorList:
		print(s)

	print("\n\n******************\n")
	print("SPECIES WITH CAS NOT FOUND IN PrIMe %d "%len(notFoundList))
	for s in notFoundList:
		print(s)
		
	#b.dom.unlink() # memory explodes if you don't do this. 
	#comment it out though if you want to play around with things after running the script